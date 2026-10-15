from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .errors import SinyaraError
from .schemas import Access, CaseInput, FollowupInput
from .store import CaseService


def create_app(service: CaseService | None = None) -> FastAPI:
    service = service or CaseService(settings)

    @asynccontextmanager
    async def lifespan(app):
        yield
        service.close()

    app = FastAPI(title="Sinyara", version="0.1.0", lifespan=lifespan)
    app.state.service = service
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","),
                       allow_credentials=False, allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["Authorization", "Content-Type", "X-Sinyara-Session"])

    @app.middleware("http")
    async def limits(request: Request, call_next):
        # Also bound chunked requests. Never read/log validation error bodies containing uploads.
        if request.method == "POST":
            length = request.headers.get("content-length")
            if length and (not length.isdigit() or int(length) > 14_100_000):
                return JSONResponse({"error": {"code": "too_large", "message": "Unggahan terlalu besar. Maksimal 10 MB audio."}}, status_code=413)
            body = bytearray()
            async for part in request.stream():
                body.extend(part)
                if len(body) > 14_100_000:
                    return JSONResponse({"error": {"code": "too_large", "message": "Unggahan terlalu besar."}}, status_code=413)
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(SinyaraError)
    async def handle_error(request, exc):
        return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse({"error": {"code": "invalid_input", "message": "Input tidak valid. Periksa batas karakter, tautan, dan ukuran audio."}}, status_code=422)

    def access(cid, authorization):
        if not authorization or not authorization.startswith("Bearer "):
            raise SinyaraError("unauthorized", "Token akses kasus diperlukan.", 401)
        return Access(case_id=cid, token=authorization[7:])

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "real", "llm_provider": settings.llm_provider,
                "llm_model": settings.llm_model, "case_ttl_seconds": settings.ttl_seconds,
                "forensic": "experimental_uncalibrated" if settings.aasist_enabled else "unavailable"}

    @app.post("/v1/cases", status_code=201)
    def create_case(data: CaseInput, x_sinyara_session: str = Header(default="")):
        return service.create(data, x_sinyara_session)

    @app.post("/v1/cases/{cid}/analyze", status_code=202)
    def analyze_case(cid: str, authorization: str = Header(default="")):
        return service.analyze(access(cid, authorization))

    @app.get("/v1/cases/{cid}")
    def get_case(cid: str, authorization: str = Header(default="")):
        return service.snapshot(access(cid, authorization))

    @app.post("/v1/cases/{cid}/followups")
    def followup(cid: str, data: FollowupInput, authorization: str = Header(default="")):
        return service.followup(access(cid, authorization), data)

    @app.delete("/v1/cases/{cid}")
    def delete_case(cid: str, authorization: str = Header(default="")):
        service.delete(access(cid, authorization))
        return {"deleted": True}

    return app


app = create_app()
