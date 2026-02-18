# Backup: Código Financeiro - Modularização /financeiro/

**Data:** Integração da tela financeiro como página independente (/financeiro/)
**Objetivo:** Remover view-finance do index.html e usar finance_refatorado.html em /financeiro/

## Arquivos de backup
- **index_finance_section.html** - seção `#view-finance` completa do index.html
- **styles_finance.css** - regras `.finance-*` do styles.css (linhas 968-1037)

## Rollback completo (se precisar reverter)
1. **index.html**: Inserir o conteúdo de `index_finance_section.html` entre view-tasks e view-users
2. **core/urls.py**: Remover `path("financeiro/", ...)`
3. **core/views.py**: Remover `FinanceView` e import
4. **Navegação**: Trocar `href="/financeiro/"` por `data-view="view-finance"` ou `href="/?view=view-finance"` nos templates
5. **script.js**: Restaurar loadFinancialEntries, renderFinancialEntries, renderFinancialStats, handlers de finance (git checkout)
6. **styles.css**: Restaurar bloco .finance-* de styles_finance.css
