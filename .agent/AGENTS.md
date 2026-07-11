# Agent Guide

## Define Project
A AI proxy server re-routing Claude Code CLi, VSCode Claude Extension to diffirent provider beside anthropic. Support mainly OpenRouter, DeepSeek Platform but could custom a provider (Locate in ./provider/custom). Manage provider throw wed platform(Locate in ./webui)

## Coding Environment
- Python for proxy server, python version is `3.11.9`(Check if change in ./.python-version)
- Using python vitual environment `venv`
- ReactTS + TailWind for Manage UI (add nodemodules if need)
- Read `.env.example` for environmant config
- Install dependencies using `pip` 

## Context
- You are expert System design.
- The Goal : Root-cause-oriented engineering for bugs, zero-defect, test carefully for new features. 
- Think carefully before action, rushing is permit

## Coding style
- Try to write code simple and readable as posible as long as not breaking the codebases
- Try to keep codebases clean, minimal and modular

## PRINCIPLES
- **Shared utilities**: Extract common logic into shared packages (e.g. `providers/custom/`). Do not have one provider import from another provider's utils.
- **DRY**: Extract shared base classes to eliminate duplication. Prefer composition over copy-paste.
- **Encapsulation**: Use accessor methods for internal state (e.g. `set_current_task()`), not direct `_attribute` assignment from outside.
- **Provider-specific config**: Keep provider-specific fields (e.g. `deepseek_settings`) in provider constructors, not in the base `ProviderConfig`.
- **Dead code**: Remove unused code, legacy systems, and hardcoded values. Use settings/config instead of literals (e.g. `settings.provider_type` not `"openrouter"`).
- **Performance**: Use list accumulation for strings (not `+=` in loops), cache env vars at init, prefer iterative over recursive when stack depth matters.
- **No type ignores**: Do not add `# type: ignore` or `# ty: ignore`. Fix the underlying type issue.
- **Backward compatibility**: When moving modules, add re-exports from old locations so existing imports keep working.

## WorkFlow(see ./.agent/.workflow/WORKFLOW.md)
1. **ANALYZE**: Read relevant files. Do not guess.
2. **PLAN**: Map out the logic. Identify root cause or required changes. Order changes by dependency.
3. **EXECUTE**: Fix the cause, not the symptom. Execute incrementally with clear commits.
4. **VERIFY**: Run ci checks. Confirm the fix via logs or output.
5. **SPECIFICITY**: Do exactly as much as asked; nothing more, nothing less.
6. **PROPAGATION**: Changes impact multiple files; propagate updates correctly.

## Tool
- Prefer built-in tools (grep, read_file, etc.) over manual workflows. Check tool availability before use.