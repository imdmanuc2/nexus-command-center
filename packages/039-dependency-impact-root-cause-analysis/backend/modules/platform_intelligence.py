from backend.services import intelligence_service as service

def analyze(query): return service.analyze(query)
def knowledge(query): return service.knowledge(query)
