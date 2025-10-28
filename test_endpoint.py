import traceback
try:
    from jewel.core.safety_enhanced import SafetySystem
    from pathlib import Path
    from jewel.config import settings
    
    data_dir = Path(settings.db_path).parent
    print(f"Data dir: {data_dir}")
    print(f"DB path: {data_dir / 'jewel_safety.db'}")
    
    safety = SafetySystem(str(data_dir / "jewel_safety.db"))
    violations = safety.get_violations(None, 100)
    print(f"Violations: {violations}")
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
