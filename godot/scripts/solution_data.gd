class_name SolutionData
extends Resource
## Contenu de la solution scellée : ce que le joueur lit une fois sorti de la salle.
##
## Purement des données, modifiables dans l'inspecteur sans toucher au code.

## Titre de l'enveloppe (« Solution scellée »).
@export var title: String = "Solution scellée"

## Texte imprimé sur le sceau, avant ouverture.
@export_multiline var seal_text: String = "À n'ouvrir qu'une fois le dossier clos."

## Verdict en une phrase, révélé en premier.
@export_multiline var verdict: String

## Chronologie révélée ligne par ligne, dans l'ordre.
@export_multiline var entries: Array[String] = []

## Citation de clôture (facultative).
@export_multiline var closing_quote: String = ""

## Auteur de la citation.
@export var quote_author: String = ""
