from flask import Blueprint, request, jsonify, send_file
from openai import OpenAI
import json
#from utils.openai_config import OPENAI_API_KEY
from flasgger import swag_from
from PIL import Image
import requests
import io


# Inicializar cliente de OpenAI (nuevo estilo v1+)
#client = OpenAI(api_key=OPENAI_API_KEY)

# OS
client = OpenAI()

api_blueprint = Blueprint("api", __name__)

def build_prompt(ingredient, type_food, maximum_calories, preparation_type, dish_style, difficulty, special_equipment, flavor_profile, course_type):
    return (
        f"Actúa como un chef profesional con años de experiencia. Crea una receta en español "
        f"que cumpla con los siguientes criterios y devuélvela **exclusivamente** en formato JSON, "
        f"\n'title': nombre de la receta,"
        f"\n'description': descripción detallada del platillo y a qué plato de qué país se asemeja o se inspira,"
        f"\n'ingredients': lista de ingredientes con cantidades,"
        f"\n'instructions': lista de pasos para la preparación,"
        f"\n'prep_time': tiempo total estimado de preparación,"
        f"\n'preparation_time': tiempo en formato time de preparación (ejemplo: 01:40:00 eso es 1 hora y 40 minutos),"
        f"\n'calories_per_serving': calorías aproximadas por porción, con breve explicación,"
        f"\n'calories': las calorías aproximadas por porción en formato integer (ejemplo: 650)."
        f"Respeta el siguiente orden y estructura de claves:\n\n"
        f"{{\n"
        f"  \"title\": string,\n"
        f"  \"description\": string,\n"
        f"  \"ingredients\": [string],\n"
        f"  \"instructions\": [string],\n"
        f"  \"prep_time\": string,\n"
        f"  \"preparation_time\": Time,\n"
        f"  \"calories_per_serving\": string,\n"
        f"  \"calories\": integer\n"
        f"}}\n\n"
        f"No agregues explicaciones ni texto adicional. Solo devuelve el JSON con los valores correspondientes.\n\n"
        f"---\n"
        f"Instrucciones para la receta:\n"
        f"- Ingredientes disponibles y sus cantidades: {ingredient}.\n"
        f"- Tipo de comida: {type_food}.\n"
        f"- Límite de calorías: {maximum_calories} kcal.\n"
        f"- Tipo de preparación: {preparation_type}.\n"
        f"- Estilo de plato o gastronomía particular: {dish_style}.\n"
        f"- Dificultad de la receta: {difficulty}.\n"
        f"- Equipamiento especial necesario: {special_equipment}.\n"
        f"- Perfil de sabor que debería dominar: {flavor_profile}.\n"
        f"- Tipo de plato: {course_type}.\n"
        f"---"
    )

@api_blueprint.route("/recipe", methods=["POST"])
@swag_from({
    'tags': ['Recetas'],
    'description': 'Genera una receta en base a los ingredientes y criterios dados.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'ingredient': {'type': 'string'},
                    'type_food': {'type': 'string'},
                    'maximum_calories': {'type': 'string'},
                    'preparation_type': {'type': 'string'},
                    'dish_style': {'type': 'string'},
                    'difficulty': {'type': 'string'},
                    'special_equipment': {'type': 'string'},
                    'flavor_profile': {'type': 'string'},
                    'course_type': {'type': 'string'}
                },
                'required': ['ingredient', 'type_food', 'maximum_calories', 'preparation_type', 'dish_style', 'difficulty', 'special_equipment', 'flavor_profile', 'course_type']
            }
        }
    ],
    'responses': {
        200: {'description': 'Receta generada exitosamente'},
        400: {'description': 'Faltan parámetros requeridos'},
        500: {'description': 'Error del servidor o de la API de OpenAI'}
    }
})
def generate_recipe():
    data = request.json

    required_params = [
        "ingredient",
        "type_food",
        "maximum_calories",
        "preparation_type",
        "dish_style",
        "difficulty",
        "special_equipment",
        "flavor_profile",
        "course_type"
    ]

    missing_params = [param for param in required_params if param not in data]

    if missing_params:
        return jsonify({"error": "Missing parameters", "missing": missing_params}), 400

    prompt = build_prompt(
        data["ingredient"],
        data["type_food"],
        data["maximum_calories"],
        data["preparation_type"],
        data["dish_style"],
        data["difficulty"],
        data["special_equipment"],
        data["flavor_profile"],
        data["course_type"]
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un chef con años de experiencia."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=5000,
            temperature=0.7
        )

        content = response.choices[0].message.content.strip()

        # Limpia si el contenido viene dentro de markdown (```json)
        if content.startswith("```"):
            content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].lstrip()

        try:
            parsed = json.loads(content)
            return jsonify(parsed)
        except json.JSONDecodeError:
            return jsonify({"error": "No se pudo parsear la respuesta como JSON.", "raw": content}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_blueprint.route("/generate-image", methods=["POST"])
@swag_from({
    'tags': ['Recetas'],
    'description': 'Genera una imagen de una receta usando DALL·E a partir del nombre, ingredientes y preparación.',
    'parameters': [
        {
            'name': 'body',
            'in': 'body',
            'required': True,
            'schema': {
                'type': 'object',
                'properties': {
                    'title': {'type': 'string'},
                    'ingredients': {'type': 'string'},
                    'preparation': {'type': 'string'}
                },
                'required': ['title', 'ingredients', 'preparation']
            }
        }
    ],
    'responses': {
        200: {
            'description': 'Imagen generada exitosamente',
            'content': {'image/png': {}}
        },
        400: {
            'description': 'Parámetros faltantes'
        },
        500: {
            'description': 'Error del servidor o del API de OpenAI'
        }
    }
})
def generate_image():
    data = request.json
    
    required_params = ['title', 'ingredients', 'preparation']
    missing = [param for param in required_params if param not in data]
    if missing:
        return jsonify({'error': 'Missing parameters', 'missing': missing}), 400
    
    title = data['title']
    ingredients = data['ingredients']
    preparation = data['preparation']
    
    prompt = f"Una fotografía realista del plato llamado '{title}', hecho con los ingredientes: {ingredients}. Se prepara así: {preparation}. Presentación profesional en un plato blanco sobre una mesa de madera clara, fondo difuminado, luz natural suave."

    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1
        )
        
        image_url = response.data[0].url

        # Descargar la imagen
        image_response = requests.get(image_url)
        image = Image.open(io.BytesIO(image_response.content))

        # Convertir a WebP y comprimir
        webp_bytes = io.BytesIO()
        image.convert("RGB").save(webp_bytes, format="WEBP", quality=80)
        webp_bytes.seek(0)

        return send_file(
            webp_bytes,
            mimetype='image/webp',
            as_attachment=False,
            download_name='receta.webp'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
