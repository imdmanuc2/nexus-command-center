def install(app):
    from backend.modules.platform_verifications import router
    app.include_router(router)
