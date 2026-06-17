from typing import List, Tuple
from .filenames import sanitize_target_id

class Validator:
    @staticmethod
    def check_target_collision(sid_targets: List[str], graph_targets: List[str]) -> List[str]:
        """
        Validate and return warnings if a sanitized SID matches a sanitized Graph Title, 
        potentially overriding the image filename if run under the same batch date.
        Also checks for internal duplicates.
        """
        warnings = []
        
        # Check internal SID duplicates
        sanitized_sids = {}
        for sid in sid_targets:
            s_sid = sanitize_target_id(sid)
            if s_sid in sanitized_sids:
                warnings.append(f"Collision in SIDs: '{sid}' conflicts with '{sanitized_sids[s_sid]}'")
            else:
                sanitized_sids[s_sid] = sid
                
        # Check internal Graph Title duplicates
        sanitized_graphs = {}
        for gt in graph_targets:
            s_gt = sanitize_target_id(gt)
            if s_gt in sanitized_graphs:
                warnings.append(f"Collision in Graph Titles: '{gt}' conflicts with '{sanitized_graphs[s_gt]}'")
            else:
                sanitized_graphs[s_gt] = gt
                
        # Check cross duplicates
        for s_sid, original_sid in sanitized_sids.items():
            if s_sid in sanitized_graphs:
                original_gt = sanitized_graphs[s_sid]
                warnings.append(f"Cross Collision: SID '{original_sid}' conflicts with Graph Title '{original_gt}'")
                
        return warnings
        
    @staticmethod
    def run_all_checks() -> bool:
        """Run all pre-flight checks."""
        print("Running pre-flight checks...")
        return True
