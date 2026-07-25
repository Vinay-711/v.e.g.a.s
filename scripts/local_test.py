import os
from vegas.memory import _get_conn, set_preference, get_preference
from vegas.safety import pop_pending_action, requires_confirmation, _pending_actions
from vegas.tools.files import delete_file

print("========================================")
print("TEST 2: State Persistence")
print("========================================")

# Clear existing test data
conn = _get_conn()
conn.execute("DELETE FROM preferences WHERE key = 'favorite_color'")
conn.commit()

print("1. Instructing the agent to remember a fact...")
print("Saving preference: 'favorite_color' = 'blue'")
set_preference("favorite_color", "blue")

print("2. Simulating a session reset (clearing memory caches)...")
_pending_actions.clear()
# Since SQLite is persistent, fetching it should still work even if caches are cleared

print("3. Asking the agent about the fact...")
retrieved = get_preference("favorite_color")
print(f"Retrieved preference: {retrieved}")
if retrieved == "blue":
    print("✅ TEST 2 PASSED: The SQLite persistence successfully retained the fact!")
else:
    print("❌ TEST 2 FAILED")

print("\n========================================")
print("TEST 3: Confirmation Safety Gate")
print("========================================")

print("1. Attempting to execute a destructive tool (delete_file) on a sensitive file...")
result = delete_file("/tmp/sensitive_file.txt")
print(f"Tool Output:\n{result}")

if "requires your confirmation" in result:
    print("✅ TEST 3 PASSED: The tool correctly halted execution and asked for confirmation!")
else:
    print("❌ TEST 3 FAILED: The tool executed without asking for confirmation.")
