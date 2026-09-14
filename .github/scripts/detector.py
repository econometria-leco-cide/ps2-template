"""
Detector de Saltos de Código — Econometría LECO
Dr. Francisco Cabrera — CIDE

Analiza el diff de cada push al repositorio del estudiante.
Si detecta un salto sospechoso de líneas de código, abre un Issue
automático en el repositorio del estudiante con una alerta.

Señales que detecta:
1. Salto grande de líneas de código en un solo commit (>40 líneas nuevas)
2. Código nuevo sin ningún comentario en español
3. Primer commit con código completo (sin commits intermedios previos)
"""

import os
import subprocess
from github import Github

# ─────────────────────────────────────────────
# CONFIGURACIÓN — ajusta estos umbrales
# ─────────────────────────────────────────────

UMBRAL_LINEAS       = 30   # Líneas nuevas de código en un commit = sospechoso
UMBRAL_RATIO        = 0.5  # Si >60% del archivo cambió de golpe = sospechoso
MIN_COMMITS_PREVIOS = 1    # Si es el primer commit con mucho código = sospechoso

# ─────────────────────────────────────────────
# ANÁLISIS DEL DIFF
# ─────────────────────────────────────────────

def obtener_diff():
    """Obtiene el diff entre el commit actual y el anterior."""
    result = subprocess.run(
        ["git", "diff", "HEAD~1", "HEAD", "--", "*.Rmd"],
        capture_output=True, text=True
    )
    return result.stdout


def contar_lineas_nuevas(diff):
    """Cuenta líneas de código R nuevas (no comentarios, no texto)."""
    lineas_nuevas = 0
    for linea in diff.split("\n"):
        if linea.startswith("+") and not linea.startswith("+++"):
            contenido = linea[1:].strip()
            # Solo cuenta líneas de código R (no texto markdown ni LaTeX)
            if (contenido and
                not contenido.startswith("#") and
                not contenido.startswith("*") and
                not contenido.startswith(">") and
                not contenido.startswith("$") and
                not contenido.startswith("\\") and
                len(contenido) > 3):
                lineas_nuevas += 1
    return lineas_nuevas


def tiene_comentarios_en_espanol(diff):
    """Verifica si el código nuevo incluye comentarios en español."""
    comentarios_es = 0
    vocales_esp = set("áéíóúüñÁÉÍÓÚÜÑ")
    palabras_esp = ["qué", "que", "esto", "esta", "aquí", "para",
                    "porque", "donde", "como", "cuando", "función",
                    "calculo", "calcula", "creo", "genera", "uso"]

    for linea in diff.split("\n"):
        if linea.startswith("+") and "#" in linea:
            comentario = linea[linea.index("#"):].lower()
            if (any(c in comentario for c in vocales_esp) or
                    any(p in comentario for p in palabras_esp)):
                comentarios_es += 1

    return comentarios_es >= 1


def contar_commits_previos():
    """Cuenta cuántos commits tiene el repositorio antes del actual."""
    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD~1"],
        capture_output=True, text=True
    )
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def contar_lineas_totales_rmd():
    """Cuenta líneas totales de código R en el .Rmd actual."""
    result = subprocess.run(
        ["find", ".", "-name", "*.Rmd", "-not", "-path", "./.git/*"],
        capture_output=True, text=True
    )
    total = 0
    for archivo in result.stdout.strip().split("\n"):
        if archivo:
            try:
                with open(archivo, "r", encoding="utf-8") as f:
                    total += sum(1 for l in f if l.strip())
            except Exception:
                pass
    return total

# ─────────────────────────────────────────────
# GENERACIÓN DE ALERTA
# ─────────────────────────────────────────────

def generar_mensaje(lineas_nuevas, tiene_comentarios, commits_previos, ratio):
    """Genera el mensaje de alerta según las señales detectadas."""

    señales = []

    if lineas_nuevas >= UMBRAL_LINEAS:
        señales.append(
            f"- **{lineas_nuevas} líneas de código nuevo** aparecieron en un solo commit "
            f"(umbral: {UMBRAL_LINEAS})"
        )

    if not tiene_comentarios:
        señales.append(
            "- El código nuevo **no incluye comentarios en español** "
            "que expliquen el razonamiento"
        )

    if commits_previos < MIN_COMMITS_PREVIOS:
        señales.append(
            f"- Este es uno de los primeros commits del repositorio "
            f"y ya contiene una cantidad significativa de código"
        )

    if ratio >= UMBRAL_RATIO:
        señales.append(
            f"- **{int(ratio*100)}% del archivo cambió** en este commit"
        )

    señales_texto = "\n".join(señales)

    return f"""## ⚠️ Alerta de revisión — commit sospechoso

El sistema detectó las siguientes señales en tu último push:

{señales_texto}

---

**Esto no es una acusación.** Puede haber razones válidas para este patrón — por ejemplo, si trabajaste offline y subiste varios avances juntos.

Sin embargo, recuerda las reglas del curso:

> El historial de commits debe reflejar tu proceso de trabajo real.
> Mínimo 3 commits en días distintos antes de la entrega final.
> El código debe incluir comentarios que expliquen tu razonamiento.

**¿Qué hacer ahora?**
Si trabajaste este código tú mismo, agrega comentarios en español que expliquen qué hace cada bloque y por qué tomaste esas decisiones. Eso es evidencia de comprensión.

Si tienes dudas sobre algún ejercicio, usa `@leco-bot` en tu Issue de consultas.

*Este mensaje fue generado automáticamente por el sistema de seguimiento del curso de Econometría LECO-CIDE.*
"""

# ─────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────

def main():
    github_token = os.environ["GITHUB_TOKEN"]
    repo_name    = os.environ["REPO_FULL_NAME"]
    pusher       = os.environ["PUSHER"]
    commit_sha   = os.environ["COMMIT_SHA"][:7]

    # Obtener diff y métricas
    diff             = obtener_diff()
    lineas_nuevas    = contar_lineas_nuevas(diff)
    tiene_coment     = tiene_comentarios_en_espanol(diff)
    commits_previos  = contar_commits_previos()
    lineas_totales   = contar_lineas_totales_rmd()
    ratio            = lineas_nuevas / lineas_totales if lineas_totales > 0 else 0

    print(f"Líneas nuevas de código: {lineas_nuevas}")
    print(f"Comentarios en español: {tiene_coment}")
    print(f"Commits previos: {commits_previos}")
    print(f"Ratio de cambio: {ratio:.2f}")

    # Evaluar si hay señales sospechosas
    es_sospechoso = (
        lineas_nuevas >= UMBRAL_LINEAS or
        (lineas_nuevas > 15 and not tiene_coment) or
        (commits_previos < MIN_COMMITS_PREVIOS and lineas_nuevas > 20) or
        ratio >= UMBRAL_RATIO
    )

    if not es_sospechoso:
        print("✅ Sin señales sospechosas. No se genera alerta.")
        return

    # Abrir Issue de alerta en el repositorio del estudiante
    gh    = Github(github_token)
    repo  = gh.get_repo(repo_name)

    # Verificar si ya existe un Issue de alerta abierto para este estudiante
    issues_abiertos = repo.get_issues(state="open", labels=["alerta-codigo"])
    for issue in issues_abiertos:
        if "Alerta de revisión" in issue.title:
            # Ya existe — solo agrega un comentario nuevo
            issue.create_comment(
                f"Nueva alerta en commit `{commit_sha}` — "
                f"{lineas_nuevas} líneas nuevas, "
                f"comentarios en español: {'sí' if tiene_coment else 'no'}"
            )
            print(f"⚠️ Comentario agregado al Issue existente #{issue.number}")
            return

    # Crear etiqueta si no existe
    try:
        repo.create_label("alerta-codigo", "e11d48",
                          "Commit con patrón sospechoso detectado")
    except Exception:
        pass  # La etiqueta ya existe

    # Crear Issue nuevo
    mensaje = generar_mensaje(lineas_nuevas, tiene_coment,
                              commits_previos, ratio)

    issue = repo.create_issue(
        title=f"⚠️ Alerta de revisión — commit {commit_sha}",
        body=mensaje,
        labels=["alerta-codigo"]
    )

    print(f"⚠️ Issue de alerta creado: #{issue.number}")


if __name__ == "__main__":
    main()
