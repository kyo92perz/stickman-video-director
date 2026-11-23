# Notas de estudo: animação 2D para os vídeos de lenda

Fontes consultadas: princípios de animação (Disney, *The Illusion of Life*, via Pluralsight, Animaker, NetGuru e VSquad) e guias de lip sync 2D (Kasra Design, Charios, LunaBloom, Percify).

## Os 12 princípios e o que falta no nosso motor

| Princípio | O que faz | Estado atual no motor | Próximo passo |
|---|---|---|---|
| Squash & stretch | Dá peso e flexibilidade, mantendo o volume | Ausente. Personagens e perna são rígidos | Esticar na subida e achatar ao pousar nos pulos da perna e do cachorro |
| Anticipation | Pequeno movimento contrário antes da ação | Ausente. Chutes e pulos começam do zero | Agachar um pouco antes do chute e antes de cada pulo |
| Staging | Enquadramento que deixa a ação clara | Parcial, com enquadramentos variados | Manter o personagem principal no terço central |
| Follow-through | Partes soltas continuam após a parada | Ausente. Cabelo e roupa não se movem | Balançar o cabelo e a barra da camisa uma fração após cada parada |
| Overlapping action | Partes do corpo se movem em ritmos diferentes | Ausente | Braço e cabeça com fases levemente diferentes |
| Slow in / slow out | Acelera e desacelera suavemente | Parcial. A câmera usa ease-out, mas os personagens não | Aplicar ease in/out ao deslocamento de personagens e objetos |
| Arcs | Movimentos em arco, não em linha reta | Ausente. Tudo se move em linha reta | Trajetória curva para o ônibus e para a perna |
| Secondary action | Pequenas ações de apoio | Parcial: piscar | Respiração, troca de peso, olhar que acompanha |
| Timing | Número de quadros define peso e emoção | Constante | Ação rápida para o susto e lenta para o suspense |
| Exaggeration | Força a emoção sem perder a leitura | Baixa | Exagerar olhos e boca nas reações-chave |
| Solid drawing | Formas com volume e equilíbrio | Baixa: formas planas sem sombreamento interno | Sombreamento em dois tons e contorno mais grosso |
| Appeal | Personagem atraente de olhar | Médio | Melhorar a silhueta de cada personagem |

## Lip sync: o que o motor faz e o que deveria fazer

- **Hoje:** a boca abre conforme o volume (RMS) da narração. Isso é um único parâmetro, sem formato de boca.
- **Guias recomendam:** cerca de 5 formas de boca (visemas): A/I/E (aberta), O/U (arredondada), M/B/P (fechada), F/V (dentes no lábio), neutra. Sons parecidos compartilham a mesma forma.
- **Plano:** mapear as vogais do texto de cada shot para essas 5 formas e distribuir as formas ao longo da duração do shot. O volume continua valendo para abrir ou fechar. A forma do visema vem do texto.

## Regras práticas que vou seguir

1. Animar primeiro o que tem mais impacto: a boca nas falas, a ação no susto, o olhar no suspense.
2. Usar timing para contar a história: pausa antes de revelar, susto curto e seco.
3. Não exagerar em todas as partes ao mesmo tempo. Uma ação forte por vez.
4. Testar cada mudança em um frame antes de renderizar o vídeo inteiro.
