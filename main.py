from celery import Celery
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
import uuid, subprocess

app = Flask(__name__)
cors = CORS(app)
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

@celery.task
def create_parallax_video(image_path: str, default_settings: dict, animation_settings: dict):
    def setting_to_arg(setting: str):
        if isinstance(setting, bool) and setting:
            return ""
        return f"--{setting}"
        
    output_video = f"static/output_{uuid.uuid4()}.mp4"

    CMD_HEADER = ["depthflow", "input", "-i", image_path]
    CMD_ANIMATION = []
    CMD_DEFAULT_SETTINGS = ["main",
                            "--time", default_settings["duration"],
                            "--fps", default_settings["framerate"],
                            "--height", default_settings["height"],
                            "--width", default_settings["width"]]
    CMD_END = ["-o", output_video]
    if animation_settings["circle"]["enabled"]:
        commands_circle = ["circle",
                           "--intensity", animation_settings["circle"]["intensity"],
                           "--reverse", setting_to_arg(animation_settings["circle"]["reverse"]), 
                           "--cumulative", setting_to_arg(animation_settings["circle"]["cumulative"]) ,
                           "--smooth", setting_to_arg(animation_settings["circle"]["smooth"]),
                           "--steady", animation_settings["circle"]["steady"],
                           "--isometric", animation_settings["circle"]["isometric"]]
        CMD_ANIMATION.extend(commands_circle)
    if animation_settings["horizontal"]["enabled"]:
        commands_horizontal = ["horizontal",
                           "--intensity", animation_settings["horizontal"]["intensity"],
                           "--reverse", setting_to_arg(animation_settings["horizontal"]["reverse"]),
                           "--cumulative", setting_to_arg(animation_settings["horizontal"]["cumulative"]),
                           "--smooth", setting_to_arg(animation_settings["horizontal"]["smooth"]),
                           "--loop", setting_to_arg(animation_settings["horizontal"]["loop"]),
                           "--steady", animation_settings["horizontal"]["steady"],
                           "--isometric", animation_settings["horizontal"]["isometric"]]
        CMD_ANIMATION.extend(commands_horizontal)
    if animation_settings["vertical"]["enabled"]:
        commands_vertical = ["vertical",
                           "--intensity", animation_settings["vertical"]["intensity"],
                           "--reverse", setting_to_arg(animation_settings["vertical"]["reverse"]),
                           "--cumulative", setting_to_arg(animation_settings["vertical"]["cumulative"]),
                           "--smooth", setting_to_arg(animation_settings["vertical"]["smooth"]),
                           "--loop", setting_to_arg(animation_settings["vertical"]["loop"]),
                           "--steady", animation_settings["vertical"]["steady"],
                           "--isometric", animation_settings["vertical"]["isometric"]]
        CMD_ANIMATION.extend(commands_vertical)
    if animation_settings["zoom"]["enabled"]:
        commands_zoom = ["zoom",
                           "--intensity", animation_settings["zoom"]["intensity"],
                           "--reverse", setting_to_arg(animation_settings["zoom"]["reverse"]),
                           "--cumulative", setting_to_arg(animation_settings["zoom"]["cumulative"]),
                           "--smooth", setting_to_arg(animation_settings["zoom"]["smooth"])]
        CMD_ANIMATION.extend(commands_zoom)
    command = [*CMD_HEADER, *CMD_ANIMATION, *CMD_DEFAULT_SETTINGS, *CMD_END]
    print(command)
    try:
        subprocess.run(command, check=True)
        return output_video
    except subprocess.CalledProcessError as e:
        return f"Error: {e}"
    except Exception as ex:
        return f"Exception: {ex}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/api/create_video', methods=['POST'])
def create_video():
    print(request.form)

    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    elif not "image/" in request.files['image'].mimetype:
        return jsonify({'error': f'Invalid file format: {request.files['image'].mimetype}'}), 400

    default_settings = {
        "duration": request.form.get("duration", "10"),
        "framerate": request.form.get("framerate", "60"),
        "height": request.form.get("height", "1080"),
        "width": request.form.get("width", "1920")
    }

    animation_settings = {
        "circle": {},
        "horizontal": {},
        "vertical": {},
        "zoom": {}
    }

    if request.form.get("circleEnabled"):
        animation_settings["circle"] = {
            "enabled": True,
            "intensity": request.form["circleIntensity"],
            "reverse": request.form["circleReverse"],
            "cumulative": request.form["circleCumulative"],
            "smooth": request.form["circleSmooth"],
            "steady": request.form["circleSteady"],
            "isometric": request.form["circleIsometric"],
        }
    else:
        animation_settings["circle"]["enabled"] = False
    if request.form.get("horizontalEnabled"):
        animation_settings["horizontal"] = {
            "enabled": True,
            "intensity": request.form["horizontalIntensity"],
            "reverse": request.form["horizontalReverse"],
            "cumulative": request.form["horizontalCumulative"],
            "smooth": request.form["horizontalSmooth"],
            "loop": True if request.form["horizontalLoop"] else "no-loop" ,
            "steady": request.form["horizontalSteady"],
            "isometric": request.form["horizontalIsometric"],
        }
    else:
        animation_settings["horizontal"]["enabled"] = False
    if request.form.get("verticalEnabled"):
        animation_settings["vertical"] = {
            "enabled": True,
            "intensity": request.form["verticalIntensity"],
            "reverse": request.form["verticalReverse"],
            "cumulative": request.form["verticalCumulative"],
            "smooth": request.form["verticalSmooth"],
            "loop": True if request.form["verticalLoop"] else "no-loop",
            "steady": request.form["verticalSteady"],
            "isometric": request.form["verticalIsometric"],
        }
    else:
        animation_settings["vertical"]["enabled"] = False
    if request.form.get("zoomEnabled"):
        animation_settings["zoom"] = {
            "enabled": True,
            "intensity": request.form["zoomIntensity"],
            "reverse": request.form["zoomReverse"],
            "cumulative": request.form["zoomCumulative"],
            "smooth": request.form["zoomSmooth"],
            "loop": True if request.form["zoomLoop"] else "no-loop",
        }
    else:
        animation_settings["zoom"]["enabled"] = False
    
    image = request.files['image']
    if image.filename == '':
        return jsonify({'error': 'No image selected'}), 400
    
    image_path = f'temp/temp_{uuid.uuid4()}.jpg'
    image.save(f'{image_path}')

    task = create_parallax_video.delay(image_path, default_settings, animation_settings)
    return jsonify({'task_id': task.id}), 202

@app.route("/api/task_status/<task_id>", methods=['GET'])
def task_status(task_id: str):
    task = celery.AsyncResult(task_id)
    if task.state == "PENDING":
        response = {
            'state': task.state,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'status': task.result,
        }
    else:
        response = {
            'state': task.state,
            'status': str(task.info)
        }
    return jsonify(response)

if __name__ == "__main__":
    app.run(port=64005, debug=True)
