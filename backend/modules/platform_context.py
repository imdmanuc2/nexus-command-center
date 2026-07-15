from backend.services.platform_context_service import read_context


def overview():
    return read_context("overview")


def home():
    return read_context("home")


def mining():
    return read_context("mining")


def infrastructure():
    return read_context("infrastructure")


def health():
    return read_context("health")
