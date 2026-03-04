from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image
from reportlab.lib.units import inch
from io import BytesIO
from fastapi.responses import StreamingResponse
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from uuid import uuid4
from datetime import datetime, date
from passlib.context import CryptContext
from datetime import timedelta
from .database import SessionLocal
from .models import BancoHoras
from pydantic import BaseModel
from .models import (
    LancamentoDia,
    BlocoAtividade,
    TipoAtividade,
    Usuario,
    FotoRelatorio
)
from . import schemas
from .models import Projeto
from fastapi import UploadFile, File
import os
import shutil
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image,
    Table, TableStyle, PageBreak
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import PageTemplate, BaseDocTemplate, Frame
from reportlab.platypus.tableofcontents import TableOfContents
from reportlab.pdfgen import canvas

import re
UPLOAD_DIR = "uploads"
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(BASE_DIR, "logo.png")

app = FastAPI()



from .database import engine
from .models import Base

Base.metadata.create_all(bind=engine)
# =========================================
# CORS
# =========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================
# DB SESSION
# =========================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def header_footer(canvas_obj, doc):
    canvas_obj.saveState()

    width, height = A4

    # ==============================
    # MARCA D'ÁGUA (logo transparente)
    # ==============================
    if os.path.exists(LOGO_PATH):
        canvas_obj.setFillAlpha(0.08)  # transparência
        canvas_obj.drawImage(
            LOGO_PATH,
            width/2 - 200,
            height/2 - 200,
            width=400,
            height=400,
            preserveAspectRatio=True,
            mask='auto'
        )
        canvas_obj.setFillAlpha(1)

    # ==============================
    # CABEÇALHO FIXO
    # ==============================
    if os.path.exists(LOGO_PATH):
        canvas_obj.drawImage(
            LOGO_PATH,
            40,
            height - 80,
            width=120,
            height=40,
            preserveAspectRatio=True,
            mask='auto'
        )

    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.drawRightString(width - 40, height - 50, "Sistema RDO WTECC")

    # ==============================
    # RODAPÉ COM PÁGINA
    # ==============================
    canvas_obj.drawRightString(
        width - 40,
        30,
        f"Página {doc.page}"
    )

    canvas_obj.restoreState()
# =========================================
# Horas HH:MM
# =========================================
def float_para_minutos(valor):
    return int(round(valor * 60))


def minutos_para_float(minutos):
    return round(minutos / 60, 2)


def minutos_para_hhmm(minutos):
    horas = minutos // 60
    mins = minutos % 60
    return f"{horas:02d}:{mins:02d}"

def float_para_hhmm(valor):
    total_minutos = int(round(valor * 60))
    horas = total_minutos // 60
    minutos = total_minutos % 60
    return f"{horas:02d}:{minutos:02d}"
# =========================================
# LOGIN
# =========================================

@app.post("/login")
def login(dados: dict, db: Session = Depends(get_db)):

    usuario = db.query(Usuario).filter(
        Usuario.email == dados["email"],
        Usuario.ativo == True
    ).first()

    if not usuario:
        raise HTTPException(status_code=400, detail="Usuário não encontrado")

    if not pwd_context.verify(dados["senha"], usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Senha incorreta")

    return {
        "id": str(usuario.id),
        "nome": usuario.nome,
        "perfil": usuario.perfil
    }

# =========================================
# CRIAR USUÁRIO
# =========================================

@app.post("/usuarios")
def criar_usuario(usuario: dict, db: Session = Depends(get_db)):

    senha_hash = pwd_context.hash(usuario["senha"])

    novo = Usuario(
        id=uuid4(),
        nome=usuario["nome"],
        email=usuario["email"],
        senha_hash=senha_hash,
        perfil=usuario["perfil"],
        ativo=True
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return {
        "id": str(novo.id),
        "nome": novo.nome,
        "perfil": novo.perfil
    }

# =========================================
# EXCLUIR USUARIO
# =========================================

@app.delete("/usuarios/{usuario_id}")
def excluir_usuario(usuario_id: str, db: Session = Depends(get_db)):

    usuario = db.query(Usuario).filter(
        Usuario.id == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if usuario.perfil == "admin":
        raise HTTPException(status_code=400, detail="Administrador não pode ser excluído")

    db.delete(usuario)
    db.commit()

    return {"mensagem": "Usuário removido com sucesso"}

# =========================================
# Anexar fotos
# =========================================

@app.post("/upload-foto/{lancamento_id}")
def upload_foto(lancamento_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.id == lancamento_id
    ).first()

    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)

    extensao = file.filename.split(".")[-1]
    nome_arquivo = f"{uuid4()}.{extensao}"
    caminho_completo = os.path.join(UPLOAD_DIR, nome_arquivo)

    with open(caminho_completo, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    nova_foto = FotoRelatorio(
        lancamento_id=lancamento.id,
        caminho=nome_arquivo
    )

    db.add(nova_foto)
    db.commit()

    return {"mensagem": "Foto enviada com sucesso"}
# =========================================
# Deletar fotos
# =========================================
@app.delete("/foto/{foto_id}")
def excluir_foto(foto_id: str, db: Session = Depends(get_db)):

    foto = db.query(FotoRelatorio).filter(
        FotoRelatorio.id == foto_id
    ).first()

    if not foto:
        raise HTTPException(status_code=404, detail="Foto não encontrada")

    caminho_arquivo = os.path.join(UPLOAD_DIR, foto.caminho)

    # 🔹 Remove arquivo físico
    if os.path.exists(caminho_arquivo):
        os.remove(caminho_arquivo)

    # 🔹 Remove do banco
    db.delete(foto)
    db.commit()

    return {"mensagem": "Foto excluída com sucesso"}

# =========================================
# EXCLUIR BLOCO
# =========================================

@app.delete("/bloco/{bloco_id}")
def excluir_bloco(bloco_id: str, db: Session = Depends(get_db)):

    bloco = db.query(BlocoAtividade).filter(
        BlocoAtividade.id == bloco_id
    ).first()

    if not bloco:
        raise HTTPException(status_code=404, detail="Bloco não encontrado")

    # Verifica se o lançamento ainda está em rascunho
    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.id == bloco.lancamento_id
    ).first()

    if lancamento.status not in ["rascunho", "reprovado"]:
        raise HTTPException(
            status_code=400,
            detail="Não é possível excluir bloco de dia já enviado"
        )

    db.delete(bloco)
    db.commit()

    return {"mensagem": "Bloco excluído com sucesso"}


# =========================================
# ATUALIZAR EMAIL
# =========================================

@app.put("/usuarios/{usuario_id}/email")
def atualizar_email(usuario_id: str, dados: dict, db: Session = Depends(get_db)):

    usuario = db.query(Usuario).filter(
        Usuario.id == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    usuario.email = dados["email"]
    db.commit()

    return {"mensagem": "Email atualizado com sucesso"}

# =========================================
# ALTERAR SENHA
# =========================================

@app.put("/usuarios/{usuario_id}/senha")
def alterar_senha(usuario_id: str, dados: dict, db: Session = Depends(get_db)):

    usuario = db.query(Usuario).filter(
        Usuario.id == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    nova_senha_hash = pwd_context.hash(dados["senha"])
    usuario.senha_hash = nova_senha_hash

    db.commit()

    return {"mensagem": "Senha alterada com sucesso"}


# =========================================
# LISTAR USUÁRIOS
# =========================================

@app.get("/usuarios")
def listar_usuarios(perfil: str = None, db: Session = Depends(get_db)):

    query = db.query(Usuario)

    if perfil:
        query = query.filter(Usuario.perfil == perfil)

    usuarios = query.all()

    return [
        {
            "id": str(u.id),
            "nome": u.nome,
            "email": u.email,
            "perfil": u.perfil
        }
        for u in usuarios
    ]

# =========================================
# CRIAR PROJETO
# =========================================

@app.post("/projetos")
def criar_projeto(dados: dict, db: Session = Depends(get_db)):

    novo = Projeto(
        nome=dados["nome"],
        cliente=dados["cliente"]
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return {
        "id": str(novo.id),
        "nome": novo.nome,
        "cliente": novo.cliente
    }

# =========================================
# LISTAR PROJETOS
# =========================================

@app.get("/projetos")
def listar_projetos(db: Session = Depends(get_db)):

    projetos = db.query(Projeto).all()

    return [
        {
            "id": str(p.id),
            "nome": p.nome,
            "cliente": p.cliente
        }
        for p in projetos
    ]

# =========================================
# EXCLUIR PROJETO
# =========================================

@app.delete("/projetos/{projeto_id}")
def excluir_projeto(projeto_id: str, db: Session = Depends(get_db)):

    projeto = db.query(Projeto).filter(
        Projeto.id == projeto_id
    ).first()

    if not projeto:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")

    db.delete(projeto)
    db.commit()

    return {"mensagem": "Projeto removido"}

# =========================================
# CÁLCULOS DE HORAS
# =========================================

def calcular_resumo(blocos_db, data_relatorio, is_feriado=False):

    from datetime import timedelta

    JORNADA_SEG_QUI = 9
    JORNADA_SEX = 8
    ADICIONAL_NOTURNO_PERCENTUAL = 0.35

    total_minutos_trabalhados = 0
    minutos_noturnos = 0
    minutos_deslocamento = 0

    dia_semana = data_relatorio.weekday()  # 0=seg ... 6=dom

    for b in blocos_db:

        inicio = b.hora_inicio
        fim = b.hora_fim

        minutos_bloco = (fim - inicio).total_seconds() / 60

        # Buscar tipo pelo nome
        tipo = b.tipo_atividade_id

        # ⚠️ Ideal seria buscar nome no banco
        # mas vamos manter simples por enquanto
        # Se seu tipo deslocamento tiver ID fixo, ajuste aqui
        # Melhor ainda: use nome no banco

        # Exemplo por nome (RECOMENDADO):
        # if b.tipo.nome.lower() == "refeição":

        # Aqui vamos assumir:
        TIPO_REFEICAO = 5
        TIPO_DESLOCAMENTO = 4  # 🔥 ajuste para o ID real

        if b.tipo_atividade_id == TIPO_REFEICAO:
            continue

        if b.tipo_atividade_id == TIPO_DESLOCAMENTO:
            minutos_deslocamento += minutos_bloco
            total_minutos_trabalhados += minutos_bloco
            continue

        total_minutos_trabalhados += minutos_bloco

        # NOTURNO
        hora_atual = inicio
        while hora_atual < fim:
            proxima = min(
                fim,
                hora_atual.replace(minute=0, second=0, microsecond=0)
                + timedelta(hours=1)
            )

            if hora_atual.hour >= 22 or hora_atual.hour < 6:
                minutos_noturnos += (proxima - hora_atual).total_seconds() / 60

            hora_atual = proxima

    horas_corridas = total_minutos_trabalhados / 60
    horas_noturnas = minutos_noturnos / 60
    horas_deslocamento = minutos_deslocamento / 60

    # ==============================
    # DEFINIR JORNADA
    # ==============================
    if is_feriado or dia_semana == 6:
        jornada = 0
    elif dia_semana == 5:
        jornada = 0
    elif dia_semana in [0, 1, 2, 3]:
        jornada = JORNADA_SEG_QUI
    elif dia_semana == 4:
        jornada = JORNADA_SEX
    else:
        jornada = 0

    horas_50_base = 0
    horas_100_base = 0

    # 🔥 EXCLUI DESLOCAMENTO DO CÁLCULO DE EXTRA
    horas_produtivas = horas_corridas - horas_deslocamento

    if is_feriado or dia_semana == 6:
        horas_100_base = horas_produtivas

    elif dia_semana == 5:
        horas_50_base = horas_produtivas

    else:
        if horas_produtivas > jornada:
            horas_50_base = horas_produtivas - jornada

    adicional_50 = horas_50_base * 0.5
    adicional_100 = horas_100_base * 1.0
    adicional_noturno = horas_noturnas * ADICIONAL_NOTURNO_PERCENTUAL

    banco_calculo = horas_corridas - jornada
    banco_positivo = adicional_50 + horas_50_base + adicional_100 + horas_100_base + adicional_noturno + horas_deslocamento if banco_calculo > 0 else 0
    banco_negativo = abs(banco_calculo) if banco_calculo < 0 else 0

    total = (
        horas_corridas
        + adicional_50
        + adicional_100
        + adicional_noturno
    )
    # 🔥 Se for folga, sobrescreve banco
    if hasattr(data_relatorio, "weekday"):
        pass
    return {
        "horas_corridas": round(horas_produtivas, 2),
        "horas_deslocamento": round(horas_deslocamento, 2),  # 🔥 NOVO
        "horas_50": round(adicional_50, 2),
        "horas_100": round(adicional_100, 2),
        "adicional_noturno": round(adicional_noturno, 2),
        "banco_positivo": round(banco_positivo, 2),
        "banco_negativo": round(banco_negativo, 2),
        "total": round(total, 2)
    }

# =========================================
# LISTAR LANÇAMENTO (FUNCIONÁRIO)
# =========================================

@app.get("/lancamento/{colaborador_id}/{data}")
def listar_lancamento(colaborador_id: str, data: date, db: Session = Depends(get_db)):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.colaborador_id == colaborador_id,
        LancamentoDia.data == data
    ).first()

    if not lancamento:
        return {
            "status": "rascunho",
            "descricao_geral": "",
            "blocos": [],
            "fotos": [],
            "resumo": {
                "horas_corridas": 0,
                "horas_deslocamento": 0,
                "horas_50": 0,
                "horas_100": 0,
                "adicional_noturno": 0,
                "banco_positivo": 0,
                "banco_negativo": 0,
                "total": 0
            },
            "motivo_reprovacao": None
        }

    # ✅ BUSCAR FOTOS AQUI (FORA DO IF)
    fotos = db.query(FotoRelatorio).filter(
        FotoRelatorio.lancamento_id == lancamento.id
    ).all()

    fotos_lista = [
    {
        "id": str(f.id),
        "url": f"/uploads/{f.caminho}"
    }
    for f in fotos
    ]


    blocos_db = db.query(BlocoAtividade).filter(
        BlocoAtividade.lancamento_id == lancamento.id
    ).order_by(BlocoAtividade.hora_inicio).all()

    resumo = calcular_resumo(
        blocos_db,
        data,
        is_feriado=lancamento.feriado
    )

    blocos = []

    for b in blocos_db:

        tipo = db.query(TipoAtividade).filter(
            TipoAtividade.id == b.tipo_atividade_id
        ).first()

        projeto = db.query(Projeto).filter(
            Projeto.id == b.projeto_id
        ).first()

        blocos.append({
            "id": str(b.id),
            "hora_inicio": b.hora_inicio,
            "hora_fim": b.hora_fim,
            "tipo_nome": tipo.nome if tipo else "",
            "projeto_nome": projeto.nome if projeto else "",
            "descricao": b.descricao,
        })

    # ===============================
    # MONTAR LISTA DE BLOCOS
    # ===============================

    blocos = []

    for b in blocos_db:

        tipo = db.query(TipoAtividade).filter(
            TipoAtividade.id == b.tipo_atividade_id
        ).first()

        projeto = db.query(Projeto).filter(
            Projeto.id == b.projeto_id
        ).first()

        blocos.append({
            "id": str(b.id),
            "hora_inicio": b.hora_inicio,
            "hora_fim": b.hora_fim,
            "tipo_nome": tipo.nome if tipo else "",
            "projeto_nome": projeto.nome if projeto else "",
            "descricao": b.descricao,
        })
        if lancamento.folga:
            dia_semana = data.weekday()

            if dia_semana in [0,1,2,3]:
                jornada = 9
            elif dia_semana == 4:
                jornada = 8
            else:
                jornada = 0

            resumo["banco_positivo"] = 0
            resumo["banco_negativo"] = jornada
    return {
    "id": str(lancamento.id),
    "status": lancamento.status,
    "descricao_geral": lancamento.descricao_geral,
    "feriado": lancamento.feriado,
    "folga": lancamento.folga,   # 👈 ADICIONE ISSO
    "blocos": blocos,
    "resumo": resumo,
    "fotos": fotos_lista,
    "motivo_reprovacao": lancamento.motivo_reprovacao

}


# =========================================
# FUNCIONÁRIO - LISTAR MEUS RELATÓRIOS
# =========================================

@app.get("/meus-relatorios/{colaborador_id}")
def meus_relatorios(colaborador_id: str, db: Session = Depends(get_db)):

    lancamentos = db.query(LancamentoDia).filter(
        LancamentoDia.colaborador_id == colaborador_id
    ).order_by(LancamentoDia.data.desc()).all()

    return [
        {
            "id": str(l.id),
            "data": l.data,
            "status": l.status,
            "motivo_reprovacao": getattr(l, "motivo_reprovacao", None)
        }
        for l in lancamentos
    ]


# =========================================
# CRIAR BLOCO
# =========================================

@app.post("/lancamento")
def criar_lancamento(dados: schemas.LancamentoInput, db: Session = Depends(get_db)):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.colaborador_id == dados.colaborador_id,
        LancamentoDia.data == dados.data
    ).first()

    # ==============================
    # SE NÃO EXISTE → CRIA
    # ==============================
    if not lancamento:
        lancamento = LancamentoDia(
            id=uuid4(),
            colaborador_id=dados.colaborador_id,
            data=dados.data,
            status="rascunho",
            descricao_geral="",
            feriado=dados.feriado
        )
        db.add(lancamento)
        db.commit()
        db.refresh(lancamento)

    else:
        # ==============================
        # SE JÁ EXISTE → ATUALIZA FERIADO
        # ==============================
        lancamento.feriado = dados.feriado
        db.commit()

    if lancamento.status not in ["rascunho", "reprovado"]:
        raise HTTPException(status_code=400, detail="Dia já enviado.")


    # ==============================
    # ADICIONAR BLOCOS
    # ==============================
    for bloco in dados.blocos:

        inicio = bloco.inicio.replace(tzinfo=None) if bloco.inicio.tzinfo else bloco.inicio
        fim = bloco.fim.replace(tzinfo=None) if bloco.fim.tzinfo else bloco.fim

        if fim <= inicio:
            raise HTTPException(status_code=400, detail="Hora fim deve ser maior que início.")

        blocos_existentes = db.query(BlocoAtividade).filter(
            BlocoAtividade.lancamento_id == lancamento.id
        ).all()

        for existente in blocos_existentes:
            if not (
                fim <= existente.hora_inicio or
                inicio >= existente.hora_fim
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Hora já lançada para este período."
                )

        novo_bloco = BlocoAtividade(
            id=uuid4(),
            lancamento_id=lancamento.id,
            projeto_id=bloco.projeto_id,
            tipo_atividade_id=bloco.tipo_id,
            hora_inicio=inicio,
            hora_fim=fim,
            descricao=bloco.descricao
        )

        db.add(novo_bloco)

    db.commit()

    return {"mensagem": "Bloco salvo com sucesso"}

# =========================================
# ATUALIZAR FERIADO
# =========================================
class FeriadoInput(BaseModel):
    feriado: bool

@app.put("/feriado/{colaborador_id}/{data}")
def atualizar_feriado(
    colaborador_id: str,
    data: date,
    dados: FeriadoInput,
    db: Session = Depends(get_db)
):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.colaborador_id == colaborador_id,
        LancamentoDia.data == data
    ).first()

    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    if lancamento.status not in ["rascunho", "reprovado"]:
        raise HTTPException(status_code=400, detail="Dia já enviado.")

    lancamento.feriado = dados.feriado
    db.commit()

    return {"mensagem": "Feriado atualizado com sucesso"}

# =========================================
# Descrição Geral
# =========================================
@app.put("/descricao/{colaborador_id}/{data}")
def salvar_descricao(
    colaborador_id: str,
    data: date,
    descricao: str,
    db: Session = Depends(get_db)
):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.colaborador_id == colaborador_id,
        LancamentoDia.data == data
    ).first()

    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    if lancamento.status not in ["rascunho", "reprovado"]:
        raise HTTPException(status_code=400, detail="Dia já enviado")

    lancamento.descricao_geral = descricao
    db.commit()

    return {"mensagem": "Descrição salva com sucesso"}

# =========================================
# FINALIZAR DIA
# =========================================

@app.put("/finalizar/{colaborador_id}/{data}")
def finalizar_dia(colaborador_id: str, data: date, db: Session = Depends(get_db)):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.colaborador_id == colaborador_id,
        LancamentoDia.data == data
    ).first()

    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    blocos = db.query(BlocoAtividade).filter(
        BlocoAtividade.lancamento_id == lancamento.id
    ).all()

    if not blocos and not lancamento.folga:
        raise HTTPException(
            status_code=400,
            detail="Dia sem blocos. Marque como Folga se aplicável."
        )

    lancamento.status = "enviado"
    db.commit()

    return {"mensagem": "Dia finalizado"}

# =========================================
# APROVAR
# =========================================

@app.put("/aprovar/{lancamento_id}")
def aprovar_lancamento(lancamento_id: str, db: Session = Depends(get_db)):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.id == lancamento_id
    ).first()

    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    if lancamento.status != "enviado":
        raise HTTPException(status_code=400, detail="Somente enviados podem ser aprovados")

    blocos = db.query(BlocoAtividade).filter(
        BlocoAtividade.lancamento_id == lancamento.id
    ).all()

    banco_positivo, banco_negativo = calcular_banco_dia(lancamento, blocos)

    registro_banco = BancoHoras(
        colaborador_id=lancamento.colaborador_id,
        lancamento_id=lancamento.id,
        data=lancamento.data,
        banco_positivo=banco_positivo,
        banco_negativo=banco_negativo,
        tipo="gerado"
    )

    db.add(registro_banco)

    lancamento.status = "aprovado"

    db.commit()

    return {"mensagem": "Aprovado e banco gerado"}


# =========================================
# REPROVAR
# =========================================



class ReprovarInput(BaseModel):
    motivo: str


@app.put("/reprovar/{lancamento_id}")
def reprovar_lancamento(
    lancamento_id: str,
    dados: ReprovarInput,
    db: Session = Depends(get_db)
):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.id == lancamento_id
    ).first()

    if not lancamento:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    # 🔥 AGORA PERMITE ENVIADO OU APROVADO
    if lancamento.status not in ["enviado", "aprovado"]:
        raise HTTPException(
            status_code=400,
            detail="Somente enviados ou aprovados podem ser reprovados"
        )

    # 🔥 Se estava aprovado, remover banco gerado
    if lancamento.status == "aprovado":
        db.query(BancoHoras).filter(
            BancoHoras.lancamento_id == lancamento.id,
            BancoHoras.tipo == "gerado"
        ).delete()

    lancamento.status = "reprovado"
    lancamento.motivo_reprovacao = dados.motivo

    db.commit()

    return {"mensagem": "Relatório reprovado e devolvido para edição"}

# =========================================
# Saldo banco
# =========================================
@app.get("/banco-horas/saldo/{colaborador_id}")
def saldo_banco(colaborador_id: str, db: Session = Depends(get_db)):

    registros = db.query(BancoHoras).filter(
        BancoHoras.colaborador_id == colaborador_id
    ).all()

    saldo = sum(r.banco_positivo - r.banco_negativo for r in registros)

    alerta = saldo > 100

    return {
        "saldo": round(saldo, 2),
        "alerta": alerta
    }

# =========================================
# Abatimento banco
# =========================================
class AbatimentoInput(BaseModel):
    colaborador_id: str
    horas: str
    descricao: str


@app.post("/banco-horas/abatimento")
def lancar_abatimento(dados: AbatimentoInput, db: Session = Depends(get_db)):

    try:
        horas, minutos = dados.horas.split(":")
        total_minutos = int(horas) * 60 + int(minutos)
    except:
        raise HTTPException(status_code=400, detail="Formato inválido. Use HH:MM")

    valor_float = total_minutos / 60

    registro = BancoHoras(
        colaborador_id=dados.colaborador_id,
        data=date.today(),
        banco_negativo=valor_float,
        tipo="abatimento"
    )

    db.add(registro)
    db.commit()

    return {"mensagem": "Horas abatidas com sucesso"}
# =========================================
# ADMIN - LISTAR RELATÓRIOS
# =========================================

@app.get("/admin/relatorios")
def listar_relatorios(
    data_inicio: date = Query(None),
    data_fim: date = Query(None),
    colaborador_id: str = Query(None),
    status: str = Query(None),
    db: Session = Depends(get_db)
):

    query = db.query(LancamentoDia)

    if data_inicio:
        query = query.filter(LancamentoDia.data >= data_inicio)

    if data_fim:
        query = query.filter(LancamentoDia.data <= data_fim)

    if colaborador_id:
        query = query.filter(LancamentoDia.colaborador_id == colaborador_id)

    if status:
        query = query.filter(LancamentoDia.status == status)

    lancamentos = query.order_by(LancamentoDia.data.desc()).all()

    resultado = []

    for l in lancamentos:
        usuario = db.query(Usuario).filter(
            Usuario.id == l.colaborador_id
        ).first()

        resultado.append({
            "id": str(l.id),
            "colaborador_id": str(l.colaborador_id),
            "colaborador_nome": usuario.nome if usuario else "",
            "data": l.data,
            "status": l.status,
            "descricao_geral": l.descricao_geral
        })

    return resultado


@app.get("/admin/pdf/{lancamento_id}")
def gerar_pdf(lancamento_id: str, db: Session = Depends(get_db)):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.id == lancamento_id
    ).first()

    if not lancamento:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    usuario = db.query(Usuario).filter(
        Usuario.id == lancamento.colaborador_id
    ).first()

    blocos = db.query(BlocoAtividade).filter(
        BlocoAtividade.lancamento_id == lancamento.id
    ).order_by(BlocoAtividade.hora_inicio).all()

    fotos = db.query(FotoRelatorio).filter(
        FotoRelatorio.lancamento_id == lancamento.id
    ).all()

    resumo = calcular_resumo(
        blocos,
        lancamento.data,
        is_feriado=lancamento.feriado
    )

    def formatar(valor):
        horas = int(valor)
        minutos = int(round((valor - horas) * 60))
        return f"{horas:02d}:{minutos:02d}"

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    doc.title = f"Relatório {usuario.nome} - {lancamento.data}"
    doc.author = "WTECC"
    doc.subject = "Relatório de Atividades"
    doc.creator = "Sistema RDO WTECC"
    elements = []

    styles = getSampleStyleSheet()

    # =============================
    # LOGO
    # =============================
    try:
        logo = Image(LOGO_PATH, width=60, height=60)
        logo.hAlign = "LEFT"
        elements.append(logo)
        elements.append(Spacer(1, 20))
    except:
        pass

    # =============================
    # CABEÇALHO
    # =============================
    elements.append(Paragraph("<b>RELATÓRIO DE ATIVIDADES</b>", styles["Title"]))
    elements.append(Spacer(1, 20))
    # =============================
    # DESTAQUE FERIADO / FOLGA
    # =============================

    if lancamento.feriado:
        elements.append(Paragraph(
            "<font color='orange'><b>DIA MARCADO COMO FERIADO</b></font>",
            styles["Normal"]
        ))
        elements.append(Spacer(1, 15))

    if lancamento.folga:
        elements.append(Paragraph(
            "<font color='red'><b>DIA MARCADO COMO FOLGA</b></font>",
            styles["Normal"]
        ))
        elements.append(Spacer(1, 15))
    elements.append(Paragraph(f"<b>Colaborador:</b> {usuario.nome}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Data:</b> {lancamento.data}", styles["Normal"]))
    elements.append(Paragraph(f"<b>Status:</b> {lancamento.status.upper()}", styles["Normal"]))
    elements.append(Spacer(1, 20))

    # =============================
    # TABELA DE ATIVIDADES
    # =============================
    data_table = [["Início", "Fim", "Projeto", "Tipo", "Descrição"]]

    for b in blocos:
        projeto = db.query(Projeto).filter(Projeto.id == b.projeto_id).first()
        tipo = db.query(TipoAtividade).filter(TipoAtividade.id == b.tipo_atividade_id).first()

        data_table.append([
            b.hora_inicio.strftime("%H:%M"),
            b.hora_fim.strftime("%H:%M"),
            projeto.nome if projeto else "",
            tipo.nome if tipo else "",
            b.descricao
        ])

    from reportlab.platypus import Table, TableStyle

    tabela = Table(data_table, repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    elements.append(tabela)
    elements.append(Spacer(1, 20))

    # =============================
    # DESCRIÇÃO GERAL
    # =============================
    elements.append(Paragraph("<b>Descrição Geral</b>", styles["Heading4"]))
    elements.append(Spacer(1, 8))

    descricao = lancamento.descricao_geral or "-"
    elements.append(Paragraph(descricao, styles["Normal"]))
    elements.append(Spacer(1, 25))

    # =============================
    # RESUMO (SEM BANCO + / -)
    # =============================
    elements.append(Paragraph("<b>Resumo de Horas</b>", styles["Heading4"]))
    elements.append(Spacer(1, 10))

    resumo_data = [
        ["Horas Corridas", formatar(resumo["horas_corridas"])],
        ["Horas Deslocamento", formatar(resumo["horas_deslocamento"])],
        ["Horas 50%", formatar(resumo["horas_50"])],
        ["Horas 100%", formatar(resumo["horas_100"])],
        ["Adicional Noturno", formatar(resumo["adicional_noturno"])],
        ["Total", formatar(resumo["total"])],
    ]

    resumo_tabela = Table(resumo_data, colWidths=[250, 100])
    resumo_tabela.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), 10),
    ]))

    elements.append(resumo_tabela)

    elements.append(Spacer(1, 30))

    # =============================
    # FOTOS DE EVIDÊNCIA (ANEXO)
    # =============================
    if fotos:
        elements.append(PageBreak())
        elements.append(Paragraph("<b>Anexo - Evidências Fotográficas</b>", styles["Heading2"]))
        elements.append(Spacer(1, 20))

        max_width = 500   # largura máxima da página
        max_height = 700  # altura máxima útil da página

        for f in fotos:
            caminho = os.path.join(UPLOAD_DIR, f.caminho)

            if os.path.exists(caminho):

                try:
                    img_reader = ImageReader(caminho)
                    original_width, original_height = img_reader.getSize()

                    # calcula proporção
                    ratio = min(
                        max_width / original_width,
                        max_height / original_height,
                        1  # nunca aumenta além do tamanho original
                    )

                    new_width = original_width * ratio
                    new_height = original_height * ratio

                    img = Image(caminho, width=new_width, height=new_height)

                    elements.append(Spacer(1, 10))
                    elements.append(img)
                    elements.append(Spacer(1, 30))

                except:
                    continue

    elements.append(Spacer(1, 40))
    elements.append(Paragraph("_________________________________________", styles["Normal"]))
    elements.append(Paragraph("Assinatura do Responsável", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    # limpar nome do funcionário (remove acentos e espaços problemáticos)
    nome_limpo = re.sub(r'[^A-Za-z0-9_]+', '_', usuario.nome)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"inline; filename=relatorio_{lancamento.data}_{nome_limpo}.pdf"
        }
    )


@app.get("/admin/relatorio/{lancamento_id}")
def admin_ver_relatorio(lancamento_id: str, db: Session = Depends(get_db)):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.id == lancamento_id
    ).first()

    if not lancamento:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")

    blocos = db.query(BlocoAtividade).filter(
        BlocoAtividade.lancamento_id == lancamento.id
    ).order_by(BlocoAtividade.hora_inicio).all()

    fotos = db.query(FotoRelatorio).filter(
        FotoRelatorio.lancamento_id == lancamento.id
    ).all()

    resumo = calcular_resumo(
        blocos,
        lancamento.data,
        is_feriado=lancamento.feriado
    )

    return {
        "id": str(lancamento.id),
        "data": lancamento.data,
        "status": lancamento.status,
        "descricao_geral": lancamento.descricao_geral,
        "motivo_reprovacao": lancamento.motivo_reprovacao,
        "feriado": lancamento.feriado,
        "folga": lancamento.folga,   
        "resumo": resumo,
        "blocos": [
    {
        "id": str(b.id),
        "hora_inicio": b.hora_inicio,
        "hora_fim": b.hora_fim,
        "descricao": b.descricao,
        "projeto_nome": db.query(Projeto).filter(
            Projeto.id == b.projeto_id
        ).first().nome if b.projeto_id else "",
        "tipo_nome": db.query(TipoAtividade).filter(
            TipoAtividade.id == b.tipo_atividade_id
        ).first().nome if b.tipo_atividade_id else "",
    }
    for b in blocos
],
        "fotos": [
            f"/uploads/{f.caminho}"
            for f in fotos
        ]
    }

def calcular_banco_dia(lancamento, blocos):

    dia_semana = lancamento.data.weekday()

    # Definir jornada corporativa
    if dia_semana in [0, 1, 2, 3]:   # Seg–Qui
        jornada = 9
    elif dia_semana == 4:           # Sexta
        jornada = 8
    else:
        jornada = 0                 # Sábado e Domingo

    # 🔥 SE FOR FOLGA → gera banco negativo igual jornada
    if lancamento.folga:
        banco_positivo = 0
        banco_negativo = jornada
        return banco_positivo, banco_negativo

    # Caso normal → usa cálculo padrão
    resumo = calcular_resumo(
        blocos,
        lancamento.data,
        is_feriado=lancamento.feriado
    )

    return resumo["banco_positivo"], resumo["banco_negativo"]



@app.get("/admin/banco-total")
def banco_total_por_funcionario(db: Session = Depends(get_db)):

    funcionarios = db.query(Usuario).filter(
        Usuario.perfil == "funcionario"
    ).all()

    resultado = []

    for usuario in funcionarios:

        registros = db.query(BancoHoras).filter(
            BancoHoras.colaborador_id == usuario.id
        ).all()

        saldo = 0

        for r in registros:
            saldo += r.banco_positivo
            saldo -= r.banco_negativo

        resultado.append({
            "id": str(usuario.id),
            "nome": usuario.nome,
            "banco_total": round(saldo, 2)
        })

    return resultado

@app.get("/banco-horas/abatimentos/{colaborador_id}")
def listar_abatimentos(colaborador_id: str, db: Session = Depends(get_db)):

    registros = db.query(BancoHoras).filter(
        BancoHoras.colaborador_id == colaborador_id,
        BancoHoras.tipo == "abatimento"
    ).order_by(BancoHoras.data.desc()).all()

    return [
        {
            "id": str(r.id),
            "horas": r.banco_negativo,
            "data": r.data,
            "created_at": r.created_at
        }
        for r in registros
    ]

@app.delete("/banco-horas/abatimento/{registro_id}")
def excluir_abatimento(registro_id: str, db: Session = Depends(get_db)):

    registro = db.query(BancoHoras).filter(
        BancoHoras.id == registro_id,
        BancoHoras.tipo == "abatimento"
    ).first()

    if not registro:
        raise HTTPException(status_code=404, detail="Abatimento não encontrado")

    db.delete(registro)
    db.commit()

    return {"mensagem": "Abatimento removido com sucesso"}

class FolgaInput(BaseModel):
    folga: bool

@app.put("/folga/{colaborador_id}/{data}")
def atualizar_folga(
    colaborador_id: str,
    data: date,
    dados: FolgaInput,
    db: Session = Depends(get_db)
):

    lancamento = db.query(LancamentoDia).filter(
        LancamentoDia.colaborador_id == colaborador_id,
        LancamentoDia.data == data
    ).first()

    # 🔥 SE NÃO EXISTIR → CRIA AUTOMATICAMENTE
    if not lancamento:
        lancamento = LancamentoDia(
            id=uuid4(),
            colaborador_id=colaborador_id,
            data=data,
            status="rascunho",
            descricao_geral="",
            feriado=False,
            folga=dados.folga
        )
        db.add(lancamento)
        db.commit()
        db.refresh(lancamento)
    else:
        lancamento.folga = dados.folga
        db.commit()
    if dados.folga and lancamento.feriado:
        raise HTTPException(
            status_code=400,
            detail="Não é permitido marcar Folga e Feriado ao mesmo tempo"
        )
    return {"mensagem": "Folga atualizada"}



@app.get("/admin/pdf-massa")
def gerar_pdf_massa(
    colaborador_id: str = Query(None),
    data_inicio: date = Query(None),
    data_fim: date = Query(None),
    projeto_id: str = Query(None),
    db: Session = Depends(get_db)

):


    buffer = BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4)



    frame = Frame(
        40, 60,
        A4[0] - 80,
        A4[1] - 140,
        id='normal'
    )

    template = PageTemplate(
        id='template',
        frames=frame,
        onPage=header_footer
    )

    doc.addPageTemplates([template])
    elementos = []
    styles = getSampleStyleSheet()

    query = db.query(LancamentoDia).filter(
        LancamentoDia.status == "aprovado"
    )

    if colaborador_id:
        query = query.filter(LancamentoDia.colaborador_id == colaborador_id)

    if data_inicio:
        query = query.filter(LancamentoDia.data >= data_inicio)

    if data_fim:
        query = query.filter(LancamentoDia.data <= data_fim)

    relatorios = query.order_by(LancamentoDia.data.asc()).all()

    data_inicio_real = relatorios[0].data
    data_fim_real = relatorios[-1].data

        # ==============================
    # METADADOS DO PDF
    # ==============================

    if colaborador_id:
        usuario_meta = db.query(Usuario).filter(
            Usuario.id == colaborador_id
        ).first()

        titulo_pdf = f"Relatório {usuario_meta.nome} - {data_inicio_real} até {data_fim_real}"
    else:
        titulo_pdf = f"Relatório Consolidado - {data_inicio_real} até {data_fim_real}"

    doc.title = titulo_pdf
    doc.author = "WTECC"
    doc.subject = "Relatório Consolidado de Atividades"
    doc.creator = "Sistema RDO WTECC"

    # ==============================
    # ACUMULADORES CONSOLIDADOS
    # ==============================
    total_corridas = 0
    total_deslocamento = 0
    total_50 = 0
    total_100 = 0
    total_noturno = 0
    total_geral = 0

    if not relatorios:
        raise HTTPException(status_code=404, detail="Nenhum relatório encontrado")
    # ==============================
    # CAPA
    # ==============================

    elementos.append(Spacer(1, 200))

    elementos.append(Paragraph(
        "<b>RELATÓRIO CONSOLIDADO DE ATIVIDADES</b>",
        styles["Title"]
    ))

    elementos.append(Spacer(1, 30))

    elementos.append(Paragraph(
        f"<b>Período:</b> {data_inicio_real} até {data_fim_real}",
        styles["Heading2"]
    ))

    if colaborador_id:
        usuario_capa = db.query(Usuario).filter(
            Usuario.id == colaborador_id
        ).first()

        elementos.append(Spacer(1, 20))
        elementos.append(Paragraph(
            f"<b>Colaborador:</b> {usuario_capa.nome}",
            styles["Heading2"]
        ))

    if projeto_id:
        projeto_meta = db.query(Projeto).filter(
            Projeto.id == projeto_id
        ).first()

        elementos.append(Spacer(1, 20))
        elementos.append(Paragraph(
            f"<b>Projeto:</b> {projeto_meta.nome}",
            styles["Heading2"]
        ))

    elementos.append(Spacer(1, 40))
    elementos.append(Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        styles["Normal"]
    ))

    elementos.append(PageBreak())

  
    for index, lancamento in enumerate(relatorios):

        usuario = db.query(Usuario).filter(
            Usuario.id == lancamento.colaborador_id
        ).first()

        query_blocos = db.query(BlocoAtividade).filter(
            BlocoAtividade.lancamento_id == lancamento.id
        )

        # 🔥 FILTRO POR PROJETO (SOMENTE NA IMPRESSÃO)
        if projeto_id:
            query_blocos = query_blocos.filter(
                BlocoAtividade.projeto_id == projeto_id
            )

        blocos = query_blocos.order_by(
            BlocoAtividade.hora_inicio
        ).all()

        # Se estiver filtrando por projeto e não houver blocos
        if projeto_id and not blocos:
            continue

        fotos = db.query(FotoRelatorio).filter(
            FotoRelatorio.lancamento_id == lancamento.id
        ).all()

        resumo = calcular_resumo(
            blocos,
            lancamento.data,
            is_feriado=lancamento.feriado
        )

        titulo_relatorio = f"{usuario.nome} - {lancamento.data}"

        elementos.append(Paragraph(titulo_relatorio, styles["Heading1"]))
        elementos[-1]._bookmarkName = titulo_relatorio

        # ==============================
        # SOMA CONSOLIDADA
        # ==============================
        total_corridas += resumo["horas_corridas"]
        total_deslocamento += resumo["horas_deslocamento"]
        total_50 += resumo["horas_50"]
        total_100 += resumo["horas_100"]
        total_noturno += resumo["adicional_noturno"]
        total_geral += resumo["total"]

     
        # ==============================
        # TABELA DE ATIVIDADES
        # ==============================
        dados_tabela = [["Início", "Fim", "Projeto", "Tipo", "Descrição"]]

        for b in blocos:
            projeto = db.query(Projeto).filter(
                Projeto.id == b.projeto_id
            ).first()

            tipo = db.query(TipoAtividade).filter(
                TipoAtividade.id == b.tipo_atividade_id
            ).first()

            dados_tabela.append([
                b.hora_inicio.strftime("%H:%M"),
                b.hora_fim.strftime("%H:%M"),
                projeto.nome if projeto else "",
                tipo.nome if tipo else "",
                b.descricao
            ])

        tabela = Table(dados_tabela, repeatRows=1)
        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
        ]))

        elementos.append(tabela)
        elementos.append(Spacer(1, 20))

        # ==============================
        # DESCRIÇÃO GERAL
        # ==============================
        elementos.append(Paragraph(
            "<b>Descrição Geral:</b>",
            styles["Normal"]
        ))

        elementos.append(Paragraph(
            lancamento.descricao_geral or "-",
            styles["Normal"]
        ))

        elementos.append(Spacer(1, 20))

        # ==============================
        # RESUMO EM TABELA HH:MM
        # ==============================
        elementos.append(Paragraph("<b>Resumo de Horas</b>", styles["Heading3"]))
        elementos.append(Spacer(1, 10))

        dados_resumo = [
            ["Horas Corridas", float_para_hhmm(resumo["horas_corridas"])],
            ["Horas Deslocamento", float_para_hhmm(resumo["horas_deslocamento"])],
            ["Horas 50%", float_para_hhmm(resumo["horas_50"])],
            ["Horas 100%", float_para_hhmm(resumo["horas_100"])],
            ["Adicional Noturno", float_para_hhmm(resumo["adicional_noturno"])],
            ["Total", float_para_hhmm(resumo["total"])],
        ]

        tabela_resumo = Table(dados_resumo, colWidths=[250, 120])
        tabela_resumo.setStyle(TableStyle([
            ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
            ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
            ("FONTSIZE", (0,0), (-1,-1), 10),
        ]))

        elementos.append(tabela_resumo)
        elementos.append(Spacer(1, 25))

        # ==============================
        # FOTOS DINÂMICAS
        # ==============================
        for f in fotos:
            caminho = os.path.join(UPLOAD_DIR, f.caminho)

            if os.path.exists(caminho):
                img = Image(caminho)
                img._restrictSize(6.5 * inch, 9 * inch)
                elementos.append(img)
                elementos.append(Spacer(1, 15))

        # ==============================
        # PAGE BREAK
        # ==============================
        if index < len(relatorios) - 1:
            elementos.append(PageBreak())

    # ==============================
    # PÁGINA FINAL CONSOLIDADA
    # ==============================
    elementos.append(PageBreak())

    elementos.append(Paragraph(
        "<b>RESUMO CONSOLIDADO DO PERÍODO</b>",
        styles["Title"]
    ))
    elementos.append(Spacer(1, 25))

    dados_consolidado = [
        ["Horas Corridas", float_para_hhmm(total_corridas)],
        ["Horas Deslocamento", float_para_hhmm(total_deslocamento)],
        ["Horas 50%", float_para_hhmm(total_50)],
        ["Horas 100%", float_para_hhmm(total_100)],
        ["Adicional Noturno", float_para_hhmm(total_noturno)],
        ["TOTAL GERAL", float_para_hhmm(total_geral)],
    ]

    tabela_final = Table(dados_consolidado, colWidths=[270, 120])
    tabela_final.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.8, colors.black),
        ("BACKGROUND", (0,0), (-1,-1), colors.whitesmoke),
        ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 11),
    ]))

    elementos.append(tabela_final)

    doc.build(elementos)
    buffer.seek(0)

    if colaborador_id:
        nome_base = re.sub(r'[^A-Za-z0-9_]+', '_', usuario_capa.nome)
    else:
        nome_base = "GERAL"

    nome_arquivo = (
        f"{nome_base}_"
        f"{data_inicio_real}_ate_{data_fim_real}.pdf"
    )

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{nome_arquivo}"'
        }
    )


import os
from fastapi.staticfiles import StaticFiles

UPLOAD_DIR = "uploads"

# 🔥 Garante que a pasta exista antes de montar
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")










