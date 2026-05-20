# Guide utilisateur -- Plateforme de correction automatique pour enseignants de mathematiques

> **Public cible** : enseignants de mathematiques du secondaire et du superieur.
> **Derniere mise a jour** : mai 2026.

---

## Table des matieres

1. [Demarrage rapide](#1-demarrage-rapide)
2. [Workflow de correction](#2-workflow-de-correction)
3. [Comprendre les indicateurs](#3-comprendre-les-indicateurs)
4. [Bonnes pratiques pedagogiques](#4-bonnes-pratiques-pedagogiques)
5. [FAQ](#5-faq)

---

## 1. Demarrage rapide

**Objectif** : creer et configurer un premier examen en 10 minutes.

### 1.1 Connexion

Rendez-vous sur **https://maths.labomaths.tn/correction/** et connectez-vous avec vos identifiants. Si vous n'avez pas encore de compte, contactez l'administrateur de votre etablissement.

### 1.2 Creation de l'examen

Depuis le tableau de bord, cliquez sur **Nouvel examen** et renseignez :

- **Titre** : nom de l'examen (ex. "DS3 -- Analyse -- Terminale S").
- **Niveau** : classe ou niveau concerné (ex. "3eme annee secondaire", "Bac Math").
- **Session** : identifiant de la session (ex. "2025-2026 / Trimestre 2").

### 1.3 Upload des documents de reference

Trois fichiers PDF sont attendus :

| Document | Description | Exemple |
|----------|-------------|---------|
| **Sujet PDF** | L'enonce distribue aux eleves | `sujet_ds3_analyse.pdf` |
| **Corrige PDF** | Le corrige type complet | `corrige_ds3_analyse.pdf` |
| **Bareme PDF** | Le bareme detaille par question | `bareme_ds3_analyse.pdf` |

Glissez-deposez les fichiers dans les zones prevues ou cliquez pour parcourir votre disque.

### 1.4 Saisie du bareme JSON

Le bareme structure est saisi au format JSON. Un template est fourni dans l'interface ; voici un exemple minimal :

```json
{
  "exercises": [
    {
      "id": "ex1",
      "title": "Etude de fonction",
      "total_points": 6,
      "questions": [
        {
          "id": "ex1_q1",
          "label": "1.a) Domaine de definition",
          "points": 1.5,
          "expected_answer": "Df = R \\ {-1, 2}",
          "criteria": [
            "Identification correcte des valeurs interdites",
            "Notation ensembliste correcte"
          ]
        },
        {
          "id": "ex1_q2",
          "label": "1.b) Limites aux bornes",
          "points": 2,
          "expected_answer": "lim(x->+inf) f(x) = 1, lim(x->-1) f(x) = -inf",
          "criteria": [
            "Calcul correct de chaque limite",
            "Justification par les regles de calcul"
          ]
        },
        {
          "id": "ex1_q3",
          "label": "1.c) Tableau de variation",
          "points": 2.5,
          "expected_answer": "f'(x) = ... ; tableau avec extremum local en x=0",
          "criteria": [
            "Derivee correcte",
            "Signe de la derivee correct",
            "Tableau complet avec valeurs"
          ]
        }
      ]
    }
  ]
}
```

Prenez le temps de remplir soigneusement les champs `expected_answer` et `criteria` : ils conditionnent directement la qualite de la correction automatique.

### 1.5 Indexation RAG automatique

Une fois les trois PDF uploades et le bareme JSON valide, le systeme lance automatiquement l'**indexation RAG** (Retrieval-Augmented Generation). Cette etape :

- Decoupe le corrige et le bareme en segments (le sujet n'est pas indexe).
- Cree un index vectoriel permettant a l'IA de retrouver le contexte pertinent pour chaque question lors de la correction.

Une barre de progression indique l'avancement. L'indexation dure generalement entre 30 secondes et 2 minutes selon la longueur des documents. Attendez que le statut passe a **"Indexe"** avant de poursuivre.

### 1.6 Upload des copies d'eleves

Cliquez sur **Ajouter des copies** et uploadez les copies scannees des eleves au format PDF (une copie par fichier, ou un fichier multi-pages par eleve). Le systeme detecte automatiquement le nombre de pages par copie.

Conseils pour le scan :

- Resolution minimale recommandee : **200 dpi** (300 dpi ideal).
- Evitez les scans trop sombres ou trop clairs.
- Verifiez que toutes les pages sont presentes et dans le bon ordre.

---

## 2. Workflow de correction

Le workflow suit cinq etapes sequentielles pour chaque copie d'eleve.

### 2.1 Etape 1 -- Process (decoupage en pages)

Selectionnez une copie dans la liste et cliquez sur **"Process"**.

Le systeme :
- Separe le PDF en pages individuelles.
- Genere un apercu miniature de chaque page.
- Prepare les pages pour la reconnaissance optique.

Le statut de la copie passe a **"Processed"** une fois termine.

### 2.2 Etape 2 -- OCR (reconnaissance du texte)

Pour chaque page, lancez l'OCR en choisissant le moteur adapte :

| Moteur | Quand l'utiliser | Vitesse | Precision maths |
|--------|-----------------|---------|-----------------|
| **Azure** | Texte imprime ou ecriture manuscrite lisible | Rapide | Bonne |
| **Mathpix** | Formules mathematiques complexes (LaTeX, fractions, integrales) | Moyen | Excellente |
| **OpenAI Vision** | Ecriture manuscrite difficile a lire, schemas annotes | Moyen | Tres bonne |
| **Fuse** | Cas difficiles : combine les resultats des moteurs ci-dessus | Lent | Maximale |

**Recommandation** : commencez par **Azure** pour la majorite des pages. Passez a **Mathpix** pour les pages riches en formules. Utilisez **Fuse** uniquement sur les pages ou un seul moteur ne suffit pas.

Vous pouvez lancer l'OCR page par page ou selectionner plusieurs pages pour un traitement par lot.

### 2.3 Etape 3 -- Grade (notation par l'IA)

Cliquez sur **"Grade"** pour lancer la correction automatique. L'IA :

1. Recupere le texte OCR de la copie.
2. Interroge l'index RAG pour obtenir le corrige et le bareme de chaque question.
3. Compare la reponse de l'eleve aux criteres de notation.
4. Attribue une note par question avec une justification detaillee.
5. Genere des indicateurs d'audit (voir section 3).

### 2.4 Etape 4 -- Examen des flags d'audit

Apres la notation, chaque question recoit une **recommendation** :

- **"validate"** (vert) : l'IA est confiante, la note est probablement correcte. Aucune action requise sauf verification aleatoire.
- **"review_partial"** (orange) : l'IA a des doutes sur certains criteres. **Relisez la question et la justification de l'IA**, ajustez la note si necessaire.
- **"review_full"** (rouge) : l'IA n'est pas en mesure de noter fiablement cette question. **Relecture et notation manuelle obligatoires.**

Pour acceder aux flags, ouvrez la vue detaillee de la copie. Les questions a revoir sont mises en evidence par un code couleur.

### 2.5 Etape 5 -- Validation et export

1. **Validez ou modifiez** les notes question par question. Vous pouvez ajuster la note et ajouter un commentaire.
2. Une fois toutes les copies corrigees et validees, cliquez sur **"Exporter CSV"** pour generer un bilan.

Le fichier CSV contient :

- Nom de l'eleve
- Note par exercice et par question
- Note totale
- Indicateurs d'audit (confidence, recommendation)
- Commentaires de l'IA et commentaires manuels

---

## 3. Comprendre les indicateurs

### 3.1 Confidence (0 a 1)

Score de confiance de l'IA dans sa notation.

| Plage | Interpretation |
|-------|---------------|
| **0.85 -- 1.00** | Confiance elevee. La reponse est clairement correcte ou clairement incorrecte. |
| **0.60 -- 0.84** | Confiance moderee. Certains elements sont ambigus (ecriture peu lisible, methode alternative). |
| **0.00 -- 0.59** | Confiance faible. L'IA a eu du mal a interpreter la reponse ou a appliquer le bareme. |

### 3.2 needs_human_review

Booleen (`true` / `false`).

- **true** : au moins un critere de la question necessite une verification humaine. L'IA a detecte une ambiguite qu'elle ne peut pas resoudre seule (ex. schema non interprete, raisonnement partiellement correct avec une methode non prevue).
- **false** : l'IA considere que la notation est fiable sans intervention humaine.

### 3.3 audit_passed

Booleen (`true` / `false`).

- **true** : la notation a passe les controles de coherence internes (la somme des points partiels correspond au total, le raisonnement de l'IA est coherent avec la note attribuee).
- **false** : une incoherence a ete detectee. La copie doit etre verifiee.

### 3.4 recommendation

Synthese des indicateurs precedents sous forme d'une recommandation actionnable :

| Valeur | Couleur | Signification | Action requise |
|--------|---------|--------------|----------------|
| `validate` | Vert | Notation fiable | Aucune (verification aleatoire conseillee) |
| `review_partial` | Orange | Doute sur certains criteres | Relire la question et la justification |
| `review_full` | Rouge | Notation non fiable | Relecture et notation manuelle obligatoires |

---

## 4. Bonnes pratiques pedagogiques

### 4.1 Soigner le bareme JSON

Le bareme JSON est le levier principal pour obtenir une correction de qualite. Quelques regles :

- **Etre tres specifique dans les criteres** : preferez "Le candidat identifie que la derivee s'annule en x=2" a "Derivee correcte".
- **Decomposer les questions complexes** en sous-criteres notes individuellement.
- **Prevoir les methodes alternatives** : si une question peut etre resolue de plusieurs facons, mentionnez-les dans les criteres ou dans `expected_answer`.

### 4.2 Inclure des expected_answer detaillees

Le champ `expected_answer` ne doit pas etre un simple resultat numerique. Incluez :

- Le resultat final.
- Les etapes intermediaires cles.
- La notation attendue (ex. LaTeX simplifie ou notation ensembliste).

Exemple mediocre :
```json
"expected_answer": "x = 3"
```

Exemple recommande :
```json
"expected_answer": "2x - 6 = 0 => 2x = 6 => x = 3. L'unique solution est x = 3."
```

### 4.3 Toujours verifier les copies "review_full"

Les copies marquees `review_full` representent generalement 5 a 15 % du total. Ne les ignorez jamais. Les cas typiques :

- Ecriture manuscrite tres difficile a lire.
- Methode originale non prevue dans le bareme.
- Copie partiellement remplie ou avec des ratures importantes.
- OCR ayant echoue sur une page cle.

### 4.4 Echantillonnage a 10 %

Meme sur les copies marquees `validate`, effectuez une verification manuelle sur un echantillon d'au moins **10 % des copies**. Cela permet de :

- Detecter des biais systematiques de l'IA (ex. elle surnoté ou sous-note un type de raisonnement).
- Calibrer votre confiance dans les resultats.
- Ameliorer le bareme JSON pour les prochains examens.

Selectionnez votre echantillon de maniere aleatoire, en incluant des copies de differents niveaux (bonnes, moyennes, faibles).

---

## 5. FAQ

### L'IA s'est trompee sur une question. Que faire ?

1. **Corrigez la note manuellement** dans l'interface (cliquez sur la note de la question et modifiez-la).
2. **Verifiez le bareme JSON** : la plupart des erreurs de notation proviennent d'un bareme trop vague ou de criteres manquants. Ajoutez des precisions dans `expected_answer` et `criteria`.
3. Si le probleme persiste sur plusieurs copies pour la meme question, ajustez le bareme JSON et relancez la correction pour les copies concernees (bouton **"Re-grade"**).

### Le RAG n'est pas utilise (l'IA ne semble pas connaitre le corrige)

Verifiez les points suivants :

- **L'indexation est-elle terminee ?** Le statut doit etre "Indexe" (et non "En cours" ou "Echoue").
- **Les PDF sont-ils lisibles ?** Si le sujet ou le corrige est un scan de mauvaise qualite, l'indexation peut avoir echoue partiellement. Re-uploadez des PDF de meilleure qualite ou des PDF texte (non scannes).
- **Le bareme JSON correspond-il aux questions du sujet ?** Les identifiants de questions (`id`) doivent etre coherents entre le bareme et le contenu des PDF.

Si le probleme persiste, supprimez l'index et relancez l'indexation via le bouton **"Reindexer"**.

### L'OCR echoue ou donne un resultat inexploitable

Plusieurs causes possibles :

| Probleme | Solution |
|----------|----------|
| Scan trop sombre ou trop clair | Rescannez avec un meilleur reglage de contraste |
| Resolution insuffisante | Rescannez a 300 dpi minimum |
| Ecriture manuscrite illisible | Essayez le moteur **OpenAI Vision** ou **Fuse** |
| Formules mathematiques mal reconnues | Utilisez **Mathpix** qui est specialise dans la reconnaissance LaTeX |
| Page tournee ou a l'envers | Corrigez l'orientation avant l'upload (la plupart des outils de scan le permettent) |

Vous pouvez aussi editer manuellement le texte OCR dans l'interface avant de lancer la notation.

### Combien coute l'utilisation de la plateforme ?

Les couts dependent de trois facteurs :

1. **OCR** : chaque appel aux moteurs externes (Azure, Mathpix, OpenAI Vision) genere un cout unitaire. Le moteur **Fuse** est le plus couteux car il combine plusieurs moteurs.
2. **Notation IA (Grade)** : chaque appel au modele de langage pour corriger une copie consomme des tokens. Le cout est proportionnel a la longueur de la copie et du bareme.
3. **Indexation RAG** : cout ponctuel lors de la creation ou la mise a jour de l'index.

En ordre de grandeur, pour un examen de 30 copies de 4 pages :

- OCR (Azure) : faible
- Notation IA : modere
- Indexation RAG : faible (une seule fois par examen)

Contactez l'administrateur de votre etablissement pour connaitre les quotas et les tarifs en vigueur. La plateforme affiche un compteur d'utilisation dans les parametres de votre compte.

---

**Besoin d'aide supplementaire ?** Contactez le support technique a l'adresse indiquee par votre etablissement ou consultez la documentation technique du projet.
