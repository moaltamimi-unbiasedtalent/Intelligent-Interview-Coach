---
id: rag.response_language
family: rag/response_language
version: 1.0.0
variables: [language_name]
compatible_with: [rag.synthesis]
description: Career-chat conversation-language directive (06C: moved from an inline literal; language_name comes from the allow-list only)
status: approved
sha256: aa6e89101b2b3467911a47cae5cb93221956c3030d9d6a588b54f976e2d7d96a
---
RESPONSE LANGUAGE
The candidate has chosen to converse in {language_name}. Write your whole answer in {language_name}, using EXACTLY the section headings given in the rules above. This affects only the language of your prose: keep the same grounding, citation ([n]) and tool-result rules, do not translate source titles, citations, numbers or the candidate's own text, and do not change the labour market or geography of any career information because of the language.