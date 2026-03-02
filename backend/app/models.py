from sqlalchemy import Column, String, Boolean, Date, DateTime, Numeric, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .database import Base
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
from sqlalchemy import Column, String

senha_hash = Column(String, nullable=False)

projeto_id = Column(UUID(as_uuid=True), ForeignKey("projetos.id"))


class LancamentoDia(Base):
    __tablename__ = "lancamentos_dia"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colaborador_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    projeto_id = Column(UUID(as_uuid=True))
    data = Column(Date)
    status = Column(String, default="rascunho")
    created_at = Column(DateTime, default=datetime.utcnow)
    descricao_geral = Column(String)
    feriado = Column(Boolean, default=False)
    motivo_reprovacao = Column(Text, nullable=True)
    folga = Column(Boolean, default=False)


class BlocoAtividade(Base):
    __tablename__ = "blocos_atividade"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lancamento_id = Column(UUID(as_uuid=True), ForeignKey("lancamentos_dia.id"))
    projeto_id = Column(UUID(as_uuid=True), ForeignKey("projetos.id"))  # 
    tipo_atividade_id = Column(Integer)
    hora_inicio = Column(DateTime)
    hora_fim = Column(DateTime)
    descricao = Column(Text)

class TipoAtividade(Base):
    __tablename__ = "tipos_atividade"

    id = Column(Integer, primary_key=True)
    nome = Column(String)
    gera_hora_extra = Column(Boolean)
    gera_adicional_noturno = Column(Boolean)
    conta_para_banco = Column(Boolean)

class ResumoCalculoDia(Base):
    __tablename__ = "resumo_calculo_dia"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lancamento_id = Column(UUID(as_uuid=True), ForeignKey("lancamentos_dia.id"), unique=True)
    horas_normais = Column(Numeric)
    horas_extra_50 = Column(Numeric)
    horas_extra_100 = Column(Numeric)
    banco_positivo = Column(Numeric)
    banco_negativo = Column(Numeric)
    horas_deslocamento = Column(Numeric)

class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    perfil = Column(String(20), nullable=False)
    ativo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Projeto(Base):
    __tablename__ = "projetos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nome = Column(String(150), nullable=False)
    cliente = Column(String(150), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class FotoRelatorio(Base):
    __tablename__ = "fotos_relatorio"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lancamento_id = Column(UUID(as_uuid=True), ForeignKey("lancamentos_dia.id"))
    caminho = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


from sqlalchemy import Column, DateTime, Float, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from uuid import uuid4


class BancoHoras(Base):
    __tablename__ = "banco_horas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    colaborador_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id"),
        nullable=False
    )

    lancamento_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lancamentos_dia.id"),
        nullable=True
    )

    data = Column(Date, nullable=False)

    banco_positivo = Column(Float, default=0)
    banco_negativo = Column(Float, default=0)

    tipo = Column(String, default="gerado")  
    # gerado = automático na aprovação
    # abatimento = lançado manualmente

    created_at = Column(DateTime, default=datetime.utcnow)



class BancoHorasMovimento(Base):
    __tablename__ = "banco_horas_movimento"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    colaborador_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    tipo = Column(String)  # "credito" ou "debito"
    horas = Column(Float)  # valor positivo
    descricao = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)