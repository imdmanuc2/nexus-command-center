from backend.db.repositories import seymour_registration_repository as repo

document={"capabilities":["telemetry.read","lifecycle.restart"]}
manager={"assetId":"asset-manager-test","assetType":"blockchain-manager","name":"Seymour Blockchain Manager"}
node={
  "assetId":"asset-node-test","assetType":"blockchain-node","name":"Seymour Bitcoin Cash Node",
  "coin":"BCH","network":"mainnet",
  "sync":{"snapshot":{"height":900000,"headers":900000,"progress_percent":100.0,"peers":8}},
}
assert repo._asset_values(manager,document)["asset_type"]=="blockchain-manager"
assert repo._asset_values(node,document)["coin"]=="BCH"
assert repo._sync_value(node["sync"],"height")==900000
assert repo._sync_value(node["sync"],"progressPercent","progress_percent")==100.0
print("SBP-017 CMDB projection verification: PASS")
