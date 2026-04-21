---
name: changelog
description: Gera ou atualiza CHANGELOG.md a partir do git log antes de um merge.
---

# Changelog

## Workflow

### 1. Verificar pré-condições
Confirme que o comando é executado a partir da raiz do repositório (onde `.git/` existe).

### 2. Executar o script
```bash
python skills/changelog/scripts/changelog.py
```

O script decide sozinho o que fazer:
- **`CHANGELOG.md` não existe** → lê todo o `git log`, cria o arquivo do zero.
- **`CHANGELOG.md` existe** → encontra a data mais recente no arquivo (`## YYYY-MM-DD`) e adiciona apenas commits posteriores a essa data.

### 3. Revisar o resultado
Abra `CHANGELOG.md` e confirme que as entradas novas estão corretas. Se necessário, edite mensagens de commit que ficaram genéricas antes de fazer o merge.

### 4. Fazer commit do changelog (opcional)
```bash
git add CHANGELOG.md
git commit -m "docs: update changelog"
```

## Formato gerado

```markdown
# Changelog

## 2026-04-20
- feat: adicionar página About Us
- fix: corrigir validação do formulário

## 2026-04-19
- feat: implementar dashboard
```

Seções ordenadas da mais recente para a mais antiga. Cada linha é o subject do commit (`git log --format=%s`).

## Constraints
- Rodar sempre a partir da raiz do repositório.
- Não edite o script para filtrar commits — filtre as mensagens na revisão manual (passo 3).
- Se `CHANGELOG.md` tiver sido editado manualmente e a data do cabeçalho `## ` mais recente for futura, o script não adicionará nada. Corrija a data manualmente antes de rodar.
- O script não faz commit automaticamente — isso é responsabilidade do analista.
