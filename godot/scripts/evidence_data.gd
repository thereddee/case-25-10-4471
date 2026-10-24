class_name EvidenceData
extends Resource
## Une pièce à conviction que le joueur peut trouver dans la salle.
##
## Purement des données : aucune logique de jeu ici. La description peut contenir
## des marqueurs de la forme {cle} qui sont remplis par GameRoom.build_format_context()
## au moment de l'affichage (ex. {pause_time}, {scream_time}).

## Identifiant unique, utilisé par les prérequis et les déclencheurs.
@export var id: StringName

## Nom affiché dans l'invite d'interaction et le journal de preuves.
@export var title: String

## Texte montré quand la pièce est examinée. Supporte les marqueurs {cle}.
@export_multiline var description: String

## Pièces à collecter AVANT que celle-ci révèle sa description.
## Tant qu'il en manque, c'est `locked_text` qui s'affiche et rien n'est collecté.
@export var requires: Array[StringName] = []

## Texte montré quand les prérequis ne sont pas remplis.
@export_multiline var locked_text: String = "Rien de notable pour l'instant."

## Icône optionnelle pour le journal de preuves (laisser vide = pas d'icône).
@export var icon: Texture2D


## Retourne les prérequis qui manquent encore dans `collected`.
func missing_requirements(collected: Array[StringName]) -> Array[StringName]:
	var missing: Array[StringName] = []
	for req in requires:
		if not collected.has(req):
			missing.append(req)
	return missing
