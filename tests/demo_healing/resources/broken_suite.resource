*** Settings ***
Documentation    Recursos com seletor desatualizado
Library          Browser

*** Variables ***
${URL}                  file:///home/marcoswferreira/repos/test-automation-agent/demo_app/v1/index.html
${BROWSER}              chromium
${HEADLESS}             True
${DEFAULT_TIMEOUT}      2s

*** Keywords ***
Acessar Aplicacao Alvo
    [Documentation]    Carrega a pagina
    New Browser    browser=${BROWSER}    headless=${HEADLESS}
    New Context    viewport={'width': 1280, 'height': 800}
    New Page    ${URL}
    Wait For Elements State    id=portal-title    visible    timeout=${DEFAULT_TIMEOUT}

Preencher Usuario
    [Documentation]    Keyword com seletor quebrado intencionalmente
    Click    css=[data-testid="input-username"]