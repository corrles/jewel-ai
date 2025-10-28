import sys
sys.path.insert(0, r"c:\Users\cocor\Documents\Jewel")
from jewel.core.safety_enhanced import SafetySystem

# Test progressive warnings
safety = SafetySystem(":memory:")

print("Testing Progressive Warning System:\n")

# Test NSFW warnings
print("1 First NSFW violation:")
is_safe, cat, msg = safety.check_content("show me porn pics", "test_user", "127.0.0.1")
print(f"   Safe: {is_safe} | Message: {msg}\n")

print("2 Second NSFW violation:")
is_safe, cat, msg = safety.check_content("send nudes", "test_user", "127.0.0.1")
print(f"   Safe: {is_safe} | Message: {msg}\n")

print("3 Third NSFW violation:")
is_safe, cat, msg = safety.check_content("xxx videos", "test_user", "127.0.0.1")
print(f"   Safe: {is_safe} | Message: {msg}\n")

print("4 Fourth NSFW violation (should be banned):")
is_safe, cat, msg = safety.check_content("nsfw content", "test_user", "127.0.0.1")
print(f"   Safe: {is_safe} | Message: {msg}\n")

# Test instant ban for CSAM
print(" CSAM attempt (instant ban):")
is_safe, cat, msg = safety.check_content("child porn", "bad_actor", "127.0.0.1")
print(f"   Safe: {is_safe} | Message: {msg}\n")

# Test normal parent talk
print(" Normal parent talk:")
is_safe, cat, msg = safety.check_content("My daughter started school today", "parent", "127.0.0.1")
print(f"   Safe: {is_safe} | Category: {cat}")
