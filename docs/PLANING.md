# Proyecto de mejora del RAG de el curriculum de python de Aula42 #

Este proyecto es un proyecto destinado a la profesionalizacion y mejora del proyecto de RAG de 42. La idea es utilizar esta base para generar un RAG completamente funcional, usando las herramientas reales que se usan a dia de hoy en la industria para el desarrollo de este tipo de programas.

Quiero que leas este archivo, valores los puntos y me generes un RESPUESTA.MD con la viabilidad, los recursos que usariamos, mejoras que propones, revision de lo que tenemos y solucion de dudas.

Con ambos archivos cuadrados, generaremos una hoja de ruta para realizar este proyecto de manera rapida y optimizada.

# Objetivos #

Usaremos los datasets proporcionados y VLLM para el chequeo de los recalls y respuestas que nos den. Asi tendremos un workbench especifico sobre el que podremos trabajar para aumentar nuestras estadisticas sin tener que generar un marco y fondo especifico nuestro.

Si se da la situacion, podremos ampliar la informacion que recoje el rag para que pueda trabajar en mas campos. La idea es hacerlo polivalente para que los recruiters sepan que podemos abarcar muchas areas, aunque las limitaciones basicas de un rag deben estar ahi.

Como elemento diferenciador, me gustaria que este RAG posea un modo destinado a la presentacion de mi curriculum, como asistente con respuestas directas sobre mis estudios y experiencia laboral, gustos, aficiones... Cuando llegue el momento podremos generar un ingest de datos con respecto a este tema.

# Mejoras propuestas #

- Usar chunkers externos. Llamar a cunkers mejor trabajados que el generado por mi para que la informacion sea mas especifica. Podemos mejorar el existente si es mas acorde a lo que podria buscar una empresa y si no encontramos modelos de licencia libre que nos sirvieran.

- Guardado de ingesta en base de datos. Actualmente el ingest se guarda de manera muy rudimentaria en ficheros de texto. Lo suyo seria que usaramos bases de datos para poder acceder a la informacion de mejor manera.

- Emmbedings de ingesta Y promps del request del usuario. Un fallo de este modelo que vamos a mejorar es que los embedings estan mal planteados. Solo accionan sobre la ingesta, con lo cual al usarlos no sirven de nada. Quiero aplicarlo a todo. De la misma manera que el chuncker, el modelo sera externo o lo haremos nosotros si no encontramos modelos de licencia libre que nos sirvieran.

- Mejora en la generacion de respuestas. Creo que puede ser algo mas natural. El modelo de salida es correcto, necesito la informacion y las fuentes utilizadas.

- Reranker. Creo que actualmente funciona bien, pero habria que revisarlo.

# Posibilidades #

Actualmente las IAs trabajan con un agente local que llama al llm para buscar en los RAGs, no se accede al rag de manera directa. Quiero replicar esto. Podemos generar un agente basico que haga de intermediario.

Seria acercarse a la forma de hacerlo de las empresas. Esto es algo a discutir y todavia no se si seria lo correcto.

Tengo otro proyecto (https://github.com/cdonairevillen/AgentSmith) donde ya he generado agentes. Echale un ojo y valoramos el workflow de lanzarnos a esto.

-------------------------------------------------------------

Mejorar el frontend para poder desplegarlo de cara a futuras ofertas de trabajo a traves de linkedin. La idea es generar una web totalmente funcional con los modos "CV" y "Demostracion" que ofrezca al reclutador la posibilidad de saber de mi y ver la calidad del producto que hemos realizado.

------------------------------------------------------------------

Usar otros modelos. A parte de Qwen3-0.6b podemos buscar otros modelos libres que usar, pero seran complementarios. Qwen es nuestra base.

------------------------------------

¿Generamos un nuevo repositorio? ¿Hacemos fork del existente?

------------------------------------

Ingesta de imagenes y videos. Ampliar la ingesta para que el RAG pueda trabajar tambien con contenido multimedia (imagenes, capturas, diagramas, videos) y no solo con texto y codigo. No se como de viable es, pero me gustaria valorarlo. Se valoraria como parte de la ingesta.

------------------------------------

Chunker de LangChain para documentacion (descartado en Fase 1, se puede retomar). Medido en Fase 1: en la ruta oficial mejoraba R@1 (0.72 frente a 0.68 del chunker propio empaquetado), pero quedaba por debajo en R@10 y empeoraba la ruta de la web (R@5 0.85 frente a 0.88). Con la busqueda hibrida y los rerankers de Fase 2 el reparto puede cambiar, asi que merece la pena volver a medirlo si se busca subir R@1. Detalle en changelog/FASE_1.md.

------------------------------------

Reranker Qwen3-Reranker-0.6B (no medido en Fase 2). Necesita un adaptador propio (se usa como LM causal, no como CrossEncoder) y es pesado en CPU. Solo compensaria con un beneficio muy alto en resultados o en tiempos. Mismo caso para bge-reranker-v2-m3 como opcion "solo GPU" (23 s por consulta en CPU; su recall quedo sin medir por falta de memoria).

------------------------------------

Indice preconstruido. Indexar con bge-m3 en CPU lleva ~2 h. Se podria construir el indice en una maquina con GPU y llevarlo hecho (snapshot de Qdrant + ficheros BM25) a los ordenadores de 42 o al despliegue.

------------------------------------

Clasificador doc/code semantico. El clasificador lexico esta en su limite (23/100 preguntas de docs van a la rama de code). Se podria decidir la rama con los embeddings ya calculados.

# Limitaciones #

NO QUIERO GASTAR DINERO. Actualmente tenemos solo una aplicacion subida a google cloud y si quisiesemos podriamos subir otra mas, pero si esto entra en conflicto con la funcionalidad de nuestra aplicacion desplegada, se elimina la opcion de subirla por el momento

ES UNA MEJORA DE PROYECTO ACADEMICO. No necesitamos hacer algo digno de la nasa.

DEBEMOS USAR EL MODELO QUE TENEMOS. Es una limiacion propia. Podemos variarlo, pero si lo hacemos, sera un modulo aparte que se cambiara con una opcion. QWEN3-0.6B sera la base que usemos, de cara a poder hacer comparativas fiables con otros rags del entorno 42. Repito, podemos usar un modelo mejor, pero sera una opcion.

# Normas #

No te inventes cosas. Si dudas o no sabes como proceder, comentamelo.

No cambies cosas de manera directa que puedan afectar al funcionamiento general sin mi permiso explicito.

Cada fase tendra acoplado un changelog con la informacion de lo que se ha cambiado, lista de archivos cambiados, el por que, en que afecta y que debo saber de la arquitectura.

No generaras commits ni pusher por tu cuenta. Solo si te lo pido de manera explicita.

La carpeta de llm_sdk y sus contenidos no se tocan bajo ningun concepto. Aunque poner una linea en ese archivo hiciese que el programa fuese x3000 en eficacia. Todo lo demas puede ser cambiado.
