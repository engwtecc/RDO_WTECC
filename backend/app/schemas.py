from pydantic import BaseModel
from datetime import datetime, date
from typing import List

class BlocoInput(BaseModel):
    projeto_id: str
    tipo_id: int
    inicio: datetime
    fim: datetime
    descricao: str

class LancamentoInput(BaseModel):
    colaborador_id: str
    data: date
    feriado: bool = False
    blocos: List[BlocoInput]



