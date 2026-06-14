"""Sementes de geracao por nicho para o batch de showcase.

Espelha o mapeamento nicho->template do plano (e de frontend/src/lib/niches.ts). `topics` sao
temas prontos para gerar video de demonstracao. O conteudo SEO completo (intro/benefits/faq)
vive so no frontend; aqui ficam apenas os campos que o pipeline de geracao precisa.
"""

NICHE_SEED: dict[str, dict] = {
    "curiosidades": {
        "template": "stock_narration",
        "style": "educational",
        "topics": [
            "5 curiosidades sobre o oceano profundo",
            "Fatos sobre o cerebro que parecem mentira",
            "Curiosidades do espaco que ninguem te contou",
            "Animais com habilidades que parecem superpoderes",
            "Invencoes acidentais que mudaram o mundo",
        ],
    },
    "religioso": {
        "template": "stock_narration",
        "style": "storytelling",
        "topics": [
            "Uma mensagem de fe para comecar o dia com esperanca",
            "Reflexao sobre gratidao e as pequenas bencaos da vida",
            "Como confiar em Deus nos momentos dificeis",
            "O poder do perdao na sua vida",
            "Uma palavra de animo para quem esta cansado",
        ],
    },
    "motivacional": {
        "template": "stock_narration",
        "style": "educational",
        "topics": [
            "A disciplina vence a motivacao todos os dias",
            "3 habitos das pessoas de alta performance",
            "Como parar de procrastinar de uma vez",
            "Por que sair da zona de conforto muda tudo",
            "O poder de nao desistir no momento dificil",
        ],
    },
    "financas": {
        "template": "stock_narration",
        "style": "educational",
        "topics": [
            "3 formas de economizar dinheiro sem perceber",
            "Como sair das dividas em 5 passos",
            "O metodo 50-30-20 para organizar o salario",
            "Habitos de quem consegue guardar dinheiro",
            "Pequenos gastos que viram uma fortuna no ano",
        ],
    },
    "historias": {
        "template": "story_time",
        "style": "storytelling",
        "topics": [
            "O misterio do navio encontrado sem tripulacao",
            "O caso real que a policia nunca conseguiu explicar",
            "Desaparecimentos que continuam sem solucao",
            "A historia por tras do lugar mais assustador do mundo",
            "A descoberta que mudou tudo no ultimo minuto",
        ],
    },
    "humor": {
        "template": "character_narration",
        "style": "comedy",
        "topics": [
            "Os animais mais sem nocao da natureza",
            "Invencoes inuteis que existem de verdade",
            "Fatos absurdos que parecem piada mas sao reais",
            "As leis mais ridiculas que ja existiram",
            "Coisas que so fazem sentido no Brasil",
        ],
    },
    "drama": {
        "template": "novelinha_historica",
        "style": "storytelling",
        "topics": [
            "O fato historico macabro que quase ninguem conhece",
            "A tragedia esquecida que mudou um pais",
            "O imperio que desapareceu da noite para o dia",
            "A batalha decidida por um unico erro",
            "A historia real por tras de uma lenda famosa",
        ],
    },
}
