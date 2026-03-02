from datetime import time

def calcular_horas(blocos, data_ref):

    horas_normais = 0
    horas_extra_50 = 0
    horas_extra_100 = 0
    banco_positivo = 0
    banco_negativo = 0
    horas_deslocamento = 0

    total_tecnico = 0
    dia_semana = data_ref.weekday()

    for bloco in blocos:
        duracao = (bloco["fim"] - bloco["inicio"]).total_seconds() / 3600

        tipo = bloco["tipo"]

        if tipo.nome == "Refeição":
            continue

        if tipo.nome == "Deslocamento":
            horas_deslocamento += duracao
            horas_normais += duracao
            continue

        total_tecnico += duracao

    if dia_semana <= 3:
        carga = 9
    elif dia_semana == 4:
        carga = 8
    elif dia_semana == 5:
        horas_extra_50 = total_tecnico
        return _retorno()
    else:
        horas_extra_100 = total_tecnico
        return _retorno()

    if total_tecnico > carga:
        horas_normais += carga
        horas_extra_50 = total_tecnico - carga
        banco_positivo = total_tecnico - carga
    else:
        horas_normais += total_tecnico
        banco_negativo = carga - total_tecnico

    return {
        "horas_normais": horas_normais,
        "horas_extra_50": horas_extra_50,
        "horas_extra_100": horas_extra_100,
        "banco_positivo": banco_positivo,
        "banco_negativo": banco_negativo,
        "horas_deslocamento": horas_deslocamento,
    }
