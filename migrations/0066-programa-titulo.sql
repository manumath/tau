-- Título que otorga cada programa (PLAN §65, etapa 2): las dos licenciaturas y las dos maestrías terminales otorgan
-- títulos distintos, y por eso son programas y no menciones. Es opcional: lo completa quien elabora el plan.
ALTER TABLE programa ADD COLUMN titulo TEXT;
