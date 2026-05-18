# HRAI Recruiting

Proyecto Django para gestionar candidatos, vacantes y postulaciones con clasificacion automatica de skills mediante IA.

## Que Hace El Sistema

HRAI Recruiting funciona como una base de sistema ATS para reclutamiento y seleccion. La aplicacion permite:

- Gestionar candidatos con su informacion personal y profesional.
- Registrar educacion, experiencia laboral y skills manuales o detectadas.
- Crear organizaciones y vacantes laborales.
- Registrar postulaciones de candidatos a vacantes.
- Ejecutar una clasificacion por IA para analizar el perfil del candidato.
- Separar automaticamente el resultado en tres grupos:
  - Skills tecnicas
  - Skills soft
  - Skills de educacion
- Guardar evidencia, confianza y trazabilidad de cada ejecucion IA.

## Modulos Principales

- Gestion de candidatos con experiencia, educacion y skills.
- Gestion de organizaciones, vacantes y requerimientos de skills.
- Registro de postulaciones y seguimiento por etapa.
- Clasificacion IA en tres grupos:
  - Skills tecnicas
  - Skills soft
  - Skills de educacion

## Funcionalidades Disponibles

- Alta, listado y detalle de candidatos desde la interfaz web.
- Registro estructurado de experiencia laboral y educacion.
- Catalogo de skills clasificadas por categoria.
- Creacion de vacantes con requerimientos de skills.
- Seguimiento del estado de postulaciones.
- Panel admin de Django para administracion completa del sistema.
- Historial de clasificaciones IA con respuesta almacenada y skills extraidas.

## Flujo De Uso

1. Crear una organizacion o empresa.
2. Crear una vacante laboral.
3. Registrar un candidato con resumen y texto del CV.
4. Agregar experiencia, educacion y skills si se desea.
5. Crear una postulacion del candidato a una vacante.
6. Ejecutar la clasificacion IA desde el detalle del candidato.
7. Revisar las skills detectadas en categorias tecnicas, soft y educacion.

## Entidades Principales

- `Candidate`: datos principales del candidato.
- `CandidateExperience`: historial laboral.
- `CandidateEducation`: formacion academica y cursos.
- `Skill`: catalogo normalizado de skills.
- `CandidateSkill`: skills asociadas al candidato.
- `Organization`: empresa o cliente.
- `JobOpening`: vacante laboral.
- `JobSkillRequirement`: skills requeridas para una vacante.
- `Application`: postulacion del candidato.
- `AIClassificationRun`: ejecucion de analisis IA.
- `AIExtractedSkill`: skill detectada por IA.

## Como Funciona La IA

- Si `OPENAI_API_KEY` esta configurada, el sistema utiliza OpenAI para clasificar el perfil del candidato.
- Si no hay API key, utiliza una heuristica local basica para no frenar el flujo.
- La informacion analizada incluye resumen, texto del CV, experiencia laboral, educacion y skills existentes.
- El resultado se persiste para auditoria y reutilizacion.

## Configuracion

1. Copiar `.env.example` a `.env`.
2. Dejar `DB_ENGINE=django.db.backends.postgresql` para usar PostgreSQL.
3. Configurar credenciales de PostgreSQL.
4. Opcionalmente agregar `OPENAI_API_KEY` para usar IA real.
5. Instalar dependencias:

```bash
python -m pip install -r requirements.txt
```

## Ejecucion

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Modo Local Sin PostgreSQL

Si todavia no tenes PostgreSQL instalado o levantado, podes validar el proyecto con SQLite:

```bash
set DB_ENGINE=django.db.backends.sqlite3
python manage.py migrate
python manage.py runserver
```

En PowerShell:

```powershell
$env:DB_ENGINE="django.db.backends.sqlite3"
python manage.py migrate
python manage.py runserver
```

## Proximas Mejoras Posibles

- Carga automatica de CV en PDF o DOCX.
- Matching candidato vs vacante con score de compatibilidad.
- API REST para integracion externa.
- Login con roles de recruiter, manager y admin.
- Filtros avanzados y dashboards con metricas.
