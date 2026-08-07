from backend.services.fleet_service import fleet
from backend.services.worker_service import workers
from backend.services.pool_service import pools
from backend.services.workload_service import workloads
from backend.services.relationship_service import relationships
from backend.services.topology_service import topology
from backend.services import home_service
from backend.services import cmdb_object_service

def fleet_summary(): return fleet()
def worker_list(): return workers()
def pool_list(): return pools()
def workload_list(): return workloads()
def relationship_list(): return relationships()
def topology_graph(): return topology()
def home(): return home_service.home()
def object_list(): return cmdb_object_service.list_objects()
def object_detail(object_type, object_id): return cmdb_object_service.object_detail(object_type, object_id)
