"""
Main orchestration module for soccer prediction pipeline.

PHASES:
  Phase 1: Data Ingestion (FBref, injuries, weather, schedules)
  Phase 2: ID Reconciliation (cross-source player matching)
  Phase 3: Feature Engineering (build training features)
  Phase 4: Model Training (classification models)
  Phase 5: Inference (real-time predictions)

USAGE:
  python -m src.main --phase all            # Run complete pipeline
  python -m src.main --phase ingest         # Just ingest data
  python -m src.main --phase features       # Build features only
  python -m src.main --help                 # Show all options
"""

import sqlite3
import logging
import argparse
from pathlib import Path
from datetime import datetime

# Data ingestion modules
from src.data.ingest_fbref import run_full_ingestion as ingest_fbref
from src.data.ingest_injuries import ingest_injuries
from src.data.ingest_weather import ingest_historical_weather
from src.data.ingest_schedule import build_schedule_metrics_table
from src.data.ingest_lineups import ingest_pl_lineups

# Database and processing modules
from src.database.schema import initialize_professional_db
from src.database.id_reconciliation import reconcile_players_across_sources, audit_id_mappings
from src.processing.feature_engineering import build_training_dataset

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = 'sports_data.db'

def init_database():
    """Initialize the database schema."""
    logger.info("=" * 60)
    logger.info("PHASE 0: DATABASE INITIALIZATION")
    logger.info("=" * 60)
    initialize_professional_db()
    logger.info("✓ Database schema initialized\n")

def run_data_ingestion(seasons=None):
    """Run all data ingestion pipelines."""
    logger.info("=" * 60)
    logger.info("PHASE 1: DATA INGESTION")
    logger.info("=" * 60)
    
    if seasons is None:
        seasons = ["2122", "2223", "2324", "2425"]
    
    # FBref ingestion (matches, player stats, team stats)
    logger.info("\n[1.1] Ingesting FBref data (matches, player stats, team stats)...")
    ingest_fbref(seasons)
    
    # Injury data ingestion
    logger.info("\n[1.2] Ingesting injury data...")
    conn = sqlite3.connect(DB_PATH)
    ingest_injuries(conn)
    
    # Weather data ingestion
    logger.info("\n[1.3] Ingesting weather data...")
    ingest_historical_weather(conn)
    
    # Schedule/travel metrics
    logger.info("\n[1.4] Computing schedule metrics...")
    build_schedule_metrics_table(conn)
    
    # Lineups ingestion
    logger.info("\n[1.5] Ingesting match lineups...")
    ingest_pl_lineups(seasons, conn)
    
    conn.close()
    logger.info("\n✓ Data ingestion complete\n")

def run_id_reconciliation():
    """Reconcile player IDs across data sources."""
    logger.info("=" * 60)
    logger.info("PHASE 2: ID RECONCILIATION & DEDUPLICATION")
    logger.info("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    logger.info("\nReconciling player IDs across FBref, Transfermarkt, etc...")
    reconcile_players_across_sources(conn, auto_merge_threshold=0.95, auto_merge=False)
    
    logger.info("\nAuditing ID mapping coverage...")
    audit = audit_id_mappings(conn)
    logger.info(f"ID Mapping Audit:")
    logger.info(f"  Total players: {audit['total_players']}")
    logger.info(f"  Mapped players: {audit['mapped_players']}")
    logger.info(f"  Coverage: {audit['coverage_percent']}%")
    logger.info(f"  By source: {audit['by_source']}")
    
    conn.close()
    logger.info("\n✓ ID reconciliation complete\n")

def run_feature_engineering(season_filter=None):
    """Build training features from ingested data."""
    logger.info("=" * 60)
    logger.info("PHASE 3: FEATURE ENGINEERING")
    logger.info("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    logger.info(f"\nBuilding training features...")
    dataset = build_training_dataset(conn, season_filter=season_filter)
    
    # Save to CSV for model training
    output_path = Path('training_features.csv')
    dataset.to_csv(output_path, index=False)
    
    logger.info(f"✓ Features built for {len(dataset)} matches")
    logger.info(f"✓ Saved to {output_path}")
    logger.info(f"  Shape: {dataset.shape}")
    logger.info(f"  Columns: {list(dataset.columns)}\n")
    
    conn.close()

def run_full_pipeline(seasons=None, include_features=True):
    """Run complete data pipeline."""
    start_time = datetime.now()
    
    logger.info("\n" + "=" * 60)
    logger.info("SOCCER PREDICTION SYSTEM - FULL PIPELINE")
    logger.info("=" * 60 + "\n")
    
    # Phase 0: Initialize
    init_database()
    
    # Phase 1: Data ingestion
    run_data_ingestion(seasons)
    
    # Phase 2: ID reconciliation
    run_id_reconciliation()
    
    # Phase 3: Feature engineering (optional)
    if include_features:
        run_feature_engineering()
    
    elapsed = datetime.now() - start_time
    logger.info("=" * 60)
    logger.info(f"✅ PIPELINE COMPLETE ({elapsed})")
    logger.info("=" * 60)
    logger.info("\nNext steps:")
    logger.info("  1. Review training_features.csv")
    logger.info("  2. Train classification model (see notebooks/)")
    logger.info("  3. Evaluate model performance")
    logger.info("  4. Deploy inference endpoint (Phase 5)")

def main():
    parser = argparse.ArgumentParser(
        description='Soccer prediction system pipeline orchestrator'
    )
    
    parser.add_argument(
        '--phase',
        choices=['all', 'init', 'ingest', 'reconcile', 'features'],
        default='all',
        help='Which phase(s) to run'
    )
    
    parser.add_argument(
        '--seasons',
        nargs='+',
        default=['2122', '2223', '2324', '2425'],
        help='Seasons to ingest (e.g., 2122 2223 2324 2425)'
    )
    
    parser.add_argument(
        '--skip-features',
        action='store_true',
        help='Skip feature engineering phase'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.phase == 'all':
        run_full_pipeline(args.seasons, include_features=not args.skip_features)
    elif args.phase == 'init':
        init_database()
    elif args.phase == 'ingest':
        init_database()
        run_data_ingestion(args.seasons)
    elif args.phase == 'reconcile':
        run_id_reconciliation()
    elif args.phase == 'features':
        run_feature_engineering()

if __name__ == "__main__":
    main()
