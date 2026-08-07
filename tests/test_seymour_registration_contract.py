import os
os.environ["NEXUS_SEYMOUR_REGISTRATION_TOKEN"]="unit-test-token"
from backend.services import seymour_registration_service
assert seymour_registration_service.authenticate("Bearer unit-test-token")
assert not seymour_registration_service.authenticate("Bearer wrong")
assert not seymour_registration_service.authenticate("")
print("SBP-017 receiver authentication contract verification: PASS")
