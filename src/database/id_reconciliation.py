"""
ID reconciliation and deduplication module.

Handles cross-source player/team matching:
- Fuzzy match players by name, birth date, position
- Merge duplicate entries in master tables
- Track confidence scores for matches
- Support manual review and override

USAGE:
    reconcile_players_across_sources(conn)
    review_uncertain_matches(conn, confidence_threshold=0.8)
"""

import sqlite3
import pandas as pd
from typing import Optional, List, Dict, Tuple
from difflib import SequenceMatcher
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def string_similarity(s1: str, s2: str) -> float:
    """Calculate string similarity 0-1 using SequenceMatcher."""
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()

def find_duplicate_players(
    conn: sqlite3.Connection,
    name_threshold: float = 0.85,
    check_birth_date: bool = True
) -> List[Tuple[int, int, float]]:
    """
    Find likely duplicate player entries in master table.
    
    Returns list of (master_id_1, master_id_2, confidence_score) tuples.
    """
    cursor = conn.cursor()
    cursor.execute('SELECT master_id, full_name, birth_date FROM players')
    players = cursor.fetchall()
    
    duplicates = []
    
    for i in range(len(players)):
        for j in range(i + 1, len(players)):
            id1, name1, date1 = players[i]
            id2, name2, date2 = players[j]
            
            # Name similarity check
            name_sim = string_similarity(name1, name2)
            if name_sim < name_threshold:
                continue
            
            # Birth date check (if available)
            if check_birth_date and date1 and date2:
                if date1 != date2:
                    continue
            
            duplicates.append((id1, id2, name_sim))
    
    return duplicates

def merge_player_records(
    conn: sqlite3.Connection,
    master_id_keep: int,
    master_id_remove: int,
    data_to_merge: Optional[Dict] = None
):
    """
    Merge two player records, keeping one and redirecting all foreign keys.
    
    Args:
        conn: Database connection
        master_id_keep: Player ID to keep
        master_id_remove: Player ID to merge into keep
        data_to_merge: Optional dict of fields to update in kept record
    """
    cursor = conn.cursor()
    
    logger.info(f"Merging player {master_id_remove} into {master_id_keep}...")
    
    # Update all foreign key references
    tables_with_fk = [
        'id_mapping',
        'team_rosters',
        'player_stats',
        'match_lineups',
        'transfers',
        'injury_records'
    ]
    
    for table in tables_with_fk:
        if table == 'id_mapping':
            col = 'master_id'
        elif table == 'transfers':
            col = 'player_id'
        else:
            col = 'player_id'
        
        cursor.execute(f'UPDATE {table} SET {col} = ? WHERE {col} = ?',
                      (master_id_keep, master_id_remove))
    
    # Update player record with merged data
    if data_to_merge:
        updates = ', '.join([f'{k} = ?' for k in data_to_merge.keys()])
        values = list(data_to_merge.values()) + [master_id_keep]
        cursor.execute(f'UPDATE players SET {updates} WHERE master_id = ?', values)
    
    # Delete the removed record
    cursor.execute('DELETE FROM players WHERE master_id = ?', (master_id_remove,))
    conn.commit()
    logger.info(f"Merge complete. Deleted player {master_id_remove}")

def match_players_across_sources(
    conn: sqlite3.Connection,
    source1: str = 'fbref',
    source2: str = 'transfermarkt'
) -> List[Dict]:
    """
    Find matching players across two data sources.
    
    Returns list of match candidates with confidence scores.
    """
    cursor = conn.cursor()
    
    # Get players from each source
    query = '''
        SELECT DISTINCT im.master_id, p.full_name, p.birth_date, p.position
        FROM id_mapping im
        JOIN players p ON im.master_id = p.master_id
        WHERE im.source_name = ?
    '''
    
    source1_players = pd.read_sql_query(query, conn, params=[source1])
    source2_players = pd.read_sql_query(query, conn, params=[source2])
    
    matches = []
    
    for _, p1 in source1_players.iterrows():
        for _, p2 in source2_players.iterrows():
            # Skip if already same master_id
            if p1['master_id'] == p2['master_id']:
                continue
            
            # Name similarity
            name_sim = string_similarity(p1['full_name'], p2['full_name'])
            if name_sim < 0.80:
                continue
            
            # Birth date similarity
            date_match = 1.0 if p1['birth_date'] == p2['birth_date'] else 0.0
            
            # Position similarity
            pos_match = 1.0 if p1['position'] == p2['position'] else 0.3
            
            # Composite confidence
            confidence = (name_sim * 0.6 + date_match * 0.3 + pos_match * 0.1)
            
            matches.append({
                'source1_id': p1['master_id'],
                'source1_name': p1['full_name'],
                'source2_id': p2['master_id'],
                'source2_name': p2['full_name'],
                'confidence': round(confidence, 2),
                'name_sim': round(name_sim, 2),
                'date_match': date_match,
                'position': p1['position']
            })
    
    return sorted(matches, key=lambda x: x['confidence'], reverse=True)

def reconcile_players_across_sources(
    conn: sqlite3.Connection,
    auto_merge_threshold: float = 0.95,
    auto_merge: bool = False
):
    """
    Reconcile player IDs across all sources.
    
    Args:
        conn: Database connection
        auto_merge_threshold: Confidence threshold for automatic merging
        auto_merge: If True, automatically merge high-confidence matches
    """
    logger.info("Starting cross-source player reconciliation...")
    
    matches = match_players_across_sources(conn)
    
    if len(matches) == 0:
        logger.info("No potential matches found")
        return
    
    high_conf = [m for m in matches if m['confidence'] >= auto_merge_threshold]
    low_conf = [m for m in matches if m['confidence'] < auto_merge_threshold]
    
    logger.info(f"Found {len(high_conf)} high-confidence matches and {len(low_conf)} uncertain matches")
    
    if auto_merge:
        for match in high_conf:
            # Keep the fbref ID (usually more authoritative)
            merge_player_records(
                conn,
                match['source1_id'],
                match['source2_id'],
                data_to_merge={'full_name': match['source1_name']}
            )
    else:
        # Log for manual review
        logger.warning(f"Manual review required for {len(low_conf)} uncertain matches:")
        for match in low_conf:
            logger.warning(
                f"  {match['source1_name']} ({match['source1_id']}) vs "
                f"{match['source2_name']} ({match['source2_id']}) - confidence: {match['confidence']}"
            )

def get_unreconciled_players(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get players with only one source ID (not yet reconciled)."""
    query = '''
        SELECT p.master_id, p.full_name, p.birth_date, COUNT(im.source_name) as source_count
        FROM players p
        LEFT JOIN id_mapping im ON p.master_id = im.master_id AND im.entity_type = 'player'
        GROUP BY p.master_id
        HAVING source_count = 1
        ORDER BY source_count
    '''
    return pd.read_sql_query(query, conn)

def audit_id_mappings(conn: sqlite3.Connection) -> Dict:
    """Generate audit report on ID mapping coverage."""
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM players')
    total_players = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT COUNT(DISTINCT master_id) FROM id_mapping WHERE entity_type = 'player'
    ''')
    mapped_players = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT source_name, COUNT(DISTINCT master_id) as count
        FROM id_mapping WHERE entity_type = 'player'
        GROUP BY source_name
    ''')
    by_source = {row[0]: row[1] for row in cursor.fetchall()}
    
    return {
        'total_players': total_players,
        'mapped_players': mapped_players,
        'coverage_percent': round(100 * mapped_players / total_players, 1) if total_players else 0,
        'by_source': by_source
    }

if __name__ == "__main__":
    conn = sqlite3.connect('sports_data.db')
    
    # Run reconciliation
    reconcile_players_across_sources(conn, auto_merge=False)
    
    # Audit report
    audit = audit_id_mappings(conn)
    logger.info(f"ID Mapping Audit: {audit['mapped_players']}/{audit['total_players']} "
                f"({audit['coverage_percent']}%) coverage")
    
    conn.close()
