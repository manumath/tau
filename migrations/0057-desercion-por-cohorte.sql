-- Deserción por cohorte (PLAN §57, decisiones del 7-nov-2026): D3.2.b y D3.4.a dejan de calcularse por año (desertores
-- del año / matriculados en el año) y pasan a la cohorte: ingresantes que la dejaron en sus primeros 3 años, contados en
-- el año en que la cifra queda firme. Solo cambia el texto de la fórmula, y solo si nadie lo editó en el marco; las cifras
-- se calculan al vuelo, salvo las de los años ya cerrados, que no se tocan.
UPDATE indicador_calidad
   SET formula = 'Ingresantes de la cohorte que la dejaron en sus primeros 3 años (retirados, o congelados que no volvieron '
              || 'en los dos ciclos siguientes) / ingresantes de la cohorte × 100. Cada año, las cohortes I y II de cuatro '
              || 'años antes, cuya cifra ya es firme.'
 WHERE fuente = 'auto:desercion'
   AND formula = 'Retirados, o congelados que no volvieron en los dos ciclos siguientes / ingresantes de la cohorte × 100.';
UPDATE indicador_calidad
   SET formula = 'Deserción de la cohorte de las mujeres − la de los hombres, en puntos porcentuales.'
 WHERE fuente = 'auto:brecha_desercion_genero'
   AND formula = 'Deserción de las mujeres − deserción de los hombres, en puntos porcentuales.';
