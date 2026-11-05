*** Settings ***
Documentation     Suite com seletor desatualizado para testar o auto-reparo do agente
Resource          resources/broken_suite.resource
Suite Teardown    Close Browser

*** Test Cases ***
Cenario Auto Reparavel
    [Documentation]    Testa a capacidade do agente de corrigir um seletor quebrado
    [Tags]    healing_test
    Acessar Aplicacao Alvo
    Preencher Usuario

