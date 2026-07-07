from backend.core.assets import get_assets_list
from backend.modules import discovery


def relationships():
    topo = discovery.topology().get("topology", {})
    assets = get_assets_list()

    pools = topo.get("pools", [])

    rels = {
        "assets": assets,
        "pools": pools,
        "relationships": []
    }

    for asset in assets:
        asset_id = asset.get("id")
        pool_id = asset.get("poolId")
        pool_host = asset.get("poolHost")

        if pool_id:
            rels["relationships"].append({
                "fromType": "asset",
                "fromId": asset_id,
                "toType": "pool",
                "toId": pool_id,
                "relationship": "mines_on"
            })

        if pool_host:
            rels["relationships"].append({
                "fromType": "asset",
                "fromId": asset_id,
                "toType": "host",
                "toId": pool_host,
                "relationship": "connected_to_host"
            })

    for pool in pools:
        pool_id = pool.get("id")
        host = pool.get("host")

        if host:
            rels["relationships"].append({
                "fromType": "pool",
                "fromId": pool_id,
                "toType": "host",
                "toId": host,
                "relationship": "hosted_on"
            })

    return rels
