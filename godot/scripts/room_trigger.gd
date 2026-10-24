class_name RoomTrigger
extends Area2D
## Zone de déclenchement environnementale (porte, fenêtre, tache de sang...).
##
## Détecte le joueur et le signale ; la racine décide si la zone est accessible selon
## `required_evidence`. Structure attendue :
##   Trigger (Area2D, calque 5 « Trigger », masque Player)
##   └── Shape (CollisionShape2D)

## Émis quand le joueur entre dans la zone.
signal player_entered(trigger: RoomTrigger)
## Émis quand le joueur sort de la zone.
signal player_exited(trigger: RoomTrigger)

## Identifiant de la zone (ex. &"door", &"window").
@export var trigger_id: StringName

## Preuves à posséder pour que la zone « réussisse ». Vide = toujours accessible.
@export var required_evidence: Array[StringName] = []

## Texte affiché quand on entre dans la zone avec tous les prérequis (vide = rien).
@export_multiline var enter_text: String = ""

## Texte affiché quand il manque des prérequis.
@export_multiline var blocked_text: String = ""

## Si vrai, la zone ne se déclenche qu'une fois avec succès.
@export var one_shot: bool = false

var _fired := false


func _ready() -> void:
	body_entered.connect(_on_body_entered)
	body_exited.connect(_on_body_exited)


## Preuves manquantes par rapport à `collected`.
func missing_evidence(collected: Array[StringName]) -> Array[StringName]:
	var missing: Array[StringName] = []
	for id in required_evidence:
		if not collected.has(id):
			missing.append(id)
	return missing


## Vrai si la zone peut encore se déclencher (respecte `one_shot`).
func can_fire() -> bool:
	return not (one_shot and _fired)


## À appeler par la racine après un déclenchement réussi.
func mark_fired() -> void:
	_fired = true


func _on_body_entered(body: Node2D) -> void:
	if body is RoomPlayer:
		player_entered.emit(self)


func _on_body_exited(body: Node2D) -> void:
	if body is RoomPlayer:
		player_exited.emit(self)
