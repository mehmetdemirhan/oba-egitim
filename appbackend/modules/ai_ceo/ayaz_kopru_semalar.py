from pydantic import BaseModel, Field


class DeployApprovalRequest(BaseModel):
    task_id: str = Field(..., min_length=5, max_length=50, description="Onaylanacak pipeline_run referansı")
    admin_gerekce: str = Field(..., min_length=10, max_length=1500, description="Canlıya alma kararı için resmi gerekçe")


class DeployApprovalResponse(BaseModel):
    task_id: str
    durum: str
    kuyruk_id: str = Field(..., description="squad_deploy_queue kayıt id'si")
    mesaj: str
