# Resposta ao ticket: Alunos somem conforme os cadastros aumentam

**Ticket:** #8F66FD95  
**Usuário:** Samuel Costa (samuelcosta.teacher@gmail.com)

---

## Mensagem para enviar ao professor

Olá Samuel,

Obrigada por reportar o problema! Investigamos o que pode estar causando os alunos sumirem ao cadastrar novos e implementamos correções preventivas.

**O que identificamos:**  
Em alguns casos, o navegador pode manter em cache a lista antiga de alunos. Quando você cadastra um novo aluno e a página recarrega a lista, o navegador às vezes devolve a versão antiga em vez de buscar os dados atualizados. Isso dá a impressão de que um aluno “sumiu”.

**O que foi corrigido:**  
- Ajustamos a forma como a lista de alunos é carregada para evitar cache desatualizado  
- Configuramos o sistema para que o navegador sempre busque a lista mais recente após criar ou editar um aluno  

**Como testar:**  
1. Faça login normalmente em [educaflowone.com.br/alunos](https://www.educaflowone.com.br/alunos/)  
2. Cadastre um novo aluno  
3. Verifique se todos os alunos aparecem na lista (incluindo os que já existiam e o recém-cadastrado)  

Se o problema continuar acontecendo, por favor nos avise e informe:  
- Quantos alunos você tinha antes de cadastrar o novo  
- Quantos aparecem na lista depois  
- Se possível, abra o DevTools (F12) → aba **Rede/Network**, cadastre um aluno e veja se a requisição para `/api/students/` retorna o número correto de alunos na resposta  

Seus dados estão seguros no banco de dados; as correções garantem que a tela sempre mostre a lista atualizada.

Qualquer dúvida, estamos à disposição!

---

## Notas internas (não enviar ao usuário)

- Correções aplicadas: cache-busting no `loadStudents()` (alunos_new.html) + header `Cache-Control` na API de listagem (StudentViewSet.list)
- Caso o problema persista, verificar no Django Admin se os alunos existem no banco para o user_id correto
- Possível causa alternativa: múltiplas abas ou sessões com comportamento inesperado
