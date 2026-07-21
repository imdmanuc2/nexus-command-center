from backend.services.deployment_service import packages_payload,jobs_payload,job_payload,register_payload,create_payload,transition_payload
def packages(q=None): return packages_payload(q)
def jobs(q=None): return jobs_payload(q)
def job(q): return job_payload(q)
def register(data): return register_payload(data)
def create(data): return create_payload(data)
def transition(data): return transition_payload(data)
