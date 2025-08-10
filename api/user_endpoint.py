from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/user")
async def get_user(request: Request):
    # Díky middleware tu je request.state.user
    user = getattr(request.state, "user", None)
    if not user:
        # teoreticky by se sem nemělo dostat, middleware by to stopnul
        return {"error": "Unauthorized"}
    return user
