-- Field-level masking (docs/enterprise.md): fields a custom role hides from its
-- holders. Empty for existing roles.
ALTER TABLE custom_roles_mt ADD COLUMN IF NOT EXISTS masked_fields Array(String) DEFAULT [] AFTER scoped;
