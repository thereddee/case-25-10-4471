class_name RoomPlayer
extends CharacterBody2D
## L'enquêteur, vu du dessus. Se déplace et vise avec un RayCast2D ce qui est devant lui.
##
## Ne sait rien des preuves ni des dialogues : il annonce sa cible courante et ses demandes
## d'interaction, GameRoom fait le reste. Structure attendue :
##   Player (CharacterBody2D, calque 2 « Player », masque World|NPC)
##   ├── Shape       (CollisionShape2D)
##   ├── Sprite      (Sprite2D)
##   ├── InteractRay (RayCast2D, masque Interactable|NPC, collide_with_areas = true)
##   └── Camera      (Camera2D)

## Émis quand l'objet visé change. `target` vaut null quand plus rien n'est à portée.
signal interact_target_changed(target: Node2D)
## Émis quand le joueur appuie sur « interagir » avec une cible valide.
signal interact_requested(target: Node2D)

## Vitesse de déplacement en pixels/seconde.
@export var move_speed: float = 140.0

## Portée du rayon d'interaction en pixels.
@export var interact_distance: float = 40.0

## Faux pendant un dialogue : plus de déplacement ni d'interaction.
@export var can_move: bool = true

## Direction initiale du regard.
@export var initial_facing: Vector2 = Vector2.DOWN

## Si vrai, le Sprite pivote vers la direction du regard (sprite vu du dessus, dessiné regard vers le bas).
@export var rotate_sprite: bool = true

## Vitesse de rotation du Sprite, en radians/seconde.
@export var turn_speed: float = 14.0

@onready var _ray: RayCast2D = $InteractRay
@onready var _sprite: Node2D = get_node_or_null(^"Sprite") as Node2D

var _facing := Vector2.DOWN
var _target: Node2D = null


func _ready() -> void:
	_facing = initial_facing.normalized() if initial_facing != Vector2.ZERO else Vector2.DOWN
	_ray.target_position = _facing * interact_distance
	if rotate_sprite and _sprite:
		_sprite.rotation = _facing_angle()


func _physics_process(delta: float) -> void:
	if not can_move:
		velocity = Vector2.ZERO
		return

	var direction := Input.get_vector("move_left", "move_right", "move_up", "move_down")
	velocity = direction * move_speed
	if direction != Vector2.ZERO:
		_facing = direction.normalized()
		_ray.target_position = _facing * interact_distance
	move_and_slide()
	_update_target()
	if rotate_sprite and _sprite:
		_sprite.rotation = rotate_toward(_sprite.rotation, _facing_angle(), turn_speed * delta)


func _unhandled_input(event: InputEvent) -> void:
	if not can_move or _target == null:
		return
	if event.is_action_pressed("interact"):
		interact_requested.emit(_target)
		get_viewport().set_input_as_handled()


## Direction du regard, utile pour orienter un sprite animé.
func facing() -> Vector2:
	return _facing


## Cible actuellement visée (Interactable ou RoomNPC), ou null.
func current_target() -> Node2D:
	return _target


func _facing_angle() -> float:
	return _facing.angle() - PI / 2.0


func _update_target() -> void:
	var hit: Node2D = null
	if _ray.is_colliding():
		hit = _ray.get_collider() as Node2D
	if hit != _target:
		_target = hit
		interact_target_changed.emit(_target)
