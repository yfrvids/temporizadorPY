import tkinter as tk
from tkinter import simpledialog, filedialog
from pathlib import Path
from pygame import mixer
import json
import os
import sys

def get_config_path():
    """Retorna la ruta del archivo de configuración según el SO."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        config_dir = os.path.join(base, "temporizador")
    else:  # linux/mac
        config_dir = os.path.join(os.path.expanduser("~"), ".config", "temporizador")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "config.json")

class TimerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Temporizador con Playlist")
        self.root.geometry("600x750")
        self.root.attributes("-topmost", True)

        mixer.init()
        mixer.set_num_channels(16)

        # Variables del temporizador
        self.total_seconds = 25 * 60
        self.remaining_seconds = self.total_seconds
        self.running = False
        self.paused = False

        # Variables de la playlist
        self.audio_folder = None
        self.playlist_items = []
        self.current_index = 0
        self.playing = False
        self.current_channel = None

        # Configuración persistente
        self.config_file = get_config_path()
        self.tasks_widgets = []  # lista de dicts con 'frame', 'var', 'entry' para cada task

        self.create_widgets()
        self.check_playlist_end()
        self.load_config()       # Cargar datos guardados

    # ---------- PERSISTENCIA ----------
    def save_config(self):
        """Guarda las tasks y la carpeta de audios en el archivo JSON."""
        config = {
            "tasks": [
                {"text": entry.get(), "checked": var.get()}
                for (var, entry, frame) in self.tasks_widgets
            ],
            "audio_folder": str(self.audio_folder) if self.audio_folder else None
        }
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando configuración: {e}")

    def load_config(self):
        """Carga la configuración guardada y restaura tasks y carpeta."""
        if not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error cargando configuración: {e}")
            return

        # Restaurar tasks
        tasks_data = config.get("tasks", [])
        for task in tasks_data:
            self.add_task(initial_text=task.get("text", ""), initial_checked=task.get("checked", False))

        # Restaurar carpeta de audios
        folder_str = config.get("audio_folder")
        if folder_str and os.path.isdir(folder_str):
            self.audio_folder = Path(folder_str)
            self.load_playlist()

    # ---------- INTERFAZ ----------
    def create_widgets(self):
        # ===== SECCIÓN TAREAS (ARRIBA) =====
        self.tasks_frame = tk.Frame(self.root)
        self.tasks_frame.pack(fill="x", padx=10, pady=5)

        tk.Label(self.tasks_frame, text="Tasks", font=("Helvetica", 12, "bold")).pack(anchor="w")

        self.tasks_list_frame = tk.Frame(self.tasks_frame)
        self.tasks_list_frame.pack(fill="x")

        self.add_task_btn = tk.Button(self.tasks_frame, text="+ Agregar Task", command=self.add_task)
        self.add_task_btn.pack(pady=5)

        # ===== SECCIÓN TEMPORIZADOR (CENTRO) =====
        timer_frame = tk.Frame(self.root)
        timer_frame.pack(pady=10)

        self.label = tk.Label(timer_frame, text=self.format_time(self.remaining_seconds),
                              font=("Helvetica", 30))
        self.label.pack()

        controls = tk.Frame(timer_frame)
        controls.pack()

        self.start_btn = tk.Button(controls, text="Iniciar", command=self.start_timer)
        self.start_btn.grid(row=0, column=0, padx=3)

        self.pause_btn = tk.Button(controls, text="Pausar", command=self.pause_timer)
        self.pause_btn.grid(row=0, column=1, padx=3)

        self.resume_btn = tk.Button(controls, text="Reanudar", command=self.resume_timer)
        self.resume_btn.grid(row=0, column=2, padx=3)

        self.reset_btn = tk.Button(controls, text="Reiniciar", command=self.reset_timer)
        self.reset_btn.grid(row=0, column=3, padx=3)

        self.edit_btn = tk.Button(timer_frame, text="Editar tiempo", command=self.edit_time)
        self.edit_btn.pack(pady=10)

        # ===== SECCIÓN PLAYLIST (ABAJO) =====
        playlist_container = tk.LabelFrame(self.root, text="Playlist", font=("Helvetica", 12, "bold"))
        playlist_container.pack(fill="both", expand=True, padx=10, pady=5)

        # Frame superior con botones de control
        top_playlist = tk.Frame(playlist_container)
        top_playlist.pack(fill="x", pady=5)

        self.select_folder_btn = tk.Button(top_playlist, text="Seleccionar carpeta", command=self.choose_folder)
        self.select_folder_btn.pack(side="left", padx=5)

        self.play_playlist_btn = tk.Button(top_playlist, text="▶ Reproducir", command=self.play_playlist)
        self.play_playlist_btn.pack(side="left", padx=5)

        self.stop_playlist_btn = tk.Button(top_playlist, text="■ Detener", command=self.stop_playlist)
        self.stop_playlist_btn.pack(side="left", padx=5)

        self.prev_btn = tk.Button(top_playlist, text="⏮ Anterior", command=self.previous_track)
        self.prev_btn.pack(side="left", padx=5)

        self.next_btn = tk.Button(top_playlist, text="⏭ Siguiente", command=self.next_track_manual)
        self.next_btn.pack(side="left", padx=5)

        self.current_song_label = tk.Label(top_playlist, text="", font=("Helvetica", 9), fg="blue")
        self.current_song_label.pack(side="left", padx=10)

        # Canvas y scrollbar para la lista de audios
        canvas_frame = tk.Frame(playlist_container)
        canvas_frame.pack(fill="both", expand=True)

        self.playlist_canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        self.playlist_scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=self.playlist_canvas.yview)
        self.playlist_canvas.configure(yscrollcommand=self.playlist_scrollbar.set)

        self.playlist_scrollbar.pack(side="right", fill="y")
        self.playlist_canvas.pack(side="left", fill="both", expand=True)

        self.playlist_interior = tk.Frame(self.playlist_canvas)
        self.playlist_canvas.create_window((0, 0), window=self.playlist_interior, anchor="nw")
        self.playlist_interior.bind("<Configure>", self.on_interior_configure)

        self.playlist_header = self.create_playlist_headers()

    def create_playlist_headers(self):
        header = tk.Frame(self.playlist_interior)
        header.pack(fill="x", pady=2)
        tk.Label(header, text="Archivo", width=35, anchor="w", font=("Helvetica", 10, "bold")).pack(side="left")
        tk.Label(header, text="Loop", width=6, anchor="center", font=("Helvetica", 10, "bold")).pack(side="left")
        tk.Label(header, text="Volumen", width=10, anchor="center", font=("Helvetica", 10, "bold")).pack(side="left")
        return header

    def on_interior_configure(self, event):
        self.playlist_canvas.configure(scrollregion=self.playlist_canvas.bbox("all"))

    # ---------- FUNCIONES DE TAREAS (con persistencia) ----------
    def add_task(self, initial_text="", initial_checked=False):
        """Agrega una nueva tarea, opcionalmente con texto y estado inicial."""
        task_frame = tk.Frame(self.tasks_list_frame)
        task_frame.pack(fill="x", pady=2)

        var = tk.BooleanVar(value=initial_checked)
        chk = tk.Checkbutton(task_frame, variable=var,
                             command=lambda: self.save_config())  # Guardar al cambiar estado
        chk.pack(side="left")

        entry = tk.Entry(task_frame)
        entry.insert(0, initial_text)
        entry.pack(side="left", fill="x", expand=True, padx=5)
        # Guardar al modificar el texto (cuando se presiona Enter o se pierde foco)
        entry.bind("<KeyRelease>", lambda e: self.save_config())

        delete_btn = tk.Button(task_frame, text="❌",
                               command=lambda f=task_frame: self.delete_task(f))
        delete_btn.pack(side="right")

        # Guardar referencia
        self.tasks_widgets.append({
            "frame": task_frame,
            "var": var,
            "entry": entry
        })

        self.save_config()  # Guardar después de agregar

    def delete_task(self, frame):
        """Elimina una tarea y actualiza la lista de widgets."""
        # Buscar el widget en la lista y eliminarlo
        for i, item in enumerate(self.tasks_widgets):
            if item["frame"] == frame:
                del self.tasks_widgets[i]
                frame.destroy()
                break
        self.save_config()

    # ---------- FUNCIONES DE PLAYLIST ----------
    def choose_folder(self):
        folder = filedialog.askdirectory(title="Selecciona carpeta con audios")
        if folder:
            self.audio_folder = Path(folder)
            self.load_playlist()
            self.save_config()  # Guardar la nueva carpeta

    def load_playlist(self):
        for widget in self.playlist_interior.winfo_children():
            if widget != self.playlist_header:
                widget.destroy()
        self.playlist_items.clear()

        if not self.audio_folder or not self.audio_folder.exists():
            return

        audio_ext = (".mp3", ".wav", ".ogg", ".flac")
        files = [f for f in self.audio_folder.iterdir() if f.suffix.lower() in audio_ext]

        if not files:
            tk.Label(self.playlist_interior, text="No se encontraron archivos de audio").pack()
            return

        for file in files:
            item_frame = tk.Frame(self.playlist_interior)
            item_frame.pack(fill="x", pady=2)

            name = file.name[:35] + "..." if len(file.name) > 35 else file.name
            tk.Label(item_frame, text=name, width=35, anchor="w").pack(side="left")

            loop_var = tk.BooleanVar()
            chk_loop = tk.Checkbutton(item_frame, variable=loop_var)
            chk_loop.pack(side="left", padx=5)

            vol_var = tk.DoubleVar(value=70)
            scale = tk.Scale(item_frame, from_=0, to=100, orient="horizontal",
                             variable=vol_var, length=100, showvalue=0,
                             command=lambda val, idx=len(self.playlist_items): self.on_volume_change(idx, float(val)))
            scale.pack(side="left", padx=5)

            self.playlist_items.append({
                "path": file,
                "loop": loop_var,
                "volume": vol_var,
                "sound": None,
                "channel": None,
                "frame": item_frame,
                "scale": scale
            })

        self.playlist_canvas.configure(scrollregion=self.playlist_canvas.bbox("all"))

    def on_volume_change(self, index, value):
        item = self.playlist_items[index]
        if item["sound"] is not None:
            item["sound"].set_volume(value / 100.0)

    def play_playlist(self):
        if not self.playlist_items:
            return
        self.stop_playlist()
        self.playing = True
        self.current_index = 0
        self.play_current()

    def stop_playlist(self):
        self.playing = False
        if self.current_channel:
            self.current_channel.stop()
            self.current_channel = None
        self.current_song_label.config(text="")

    def play_current(self):
        if not self.playing or self.current_index >= len(self.playlist_items):
            self.playing = False
            self.current_song_label.config(text="")
            return

        item = self.playlist_items[self.current_index]

        if self.current_channel:
            self.current_channel.stop()

        if item["sound"] is None:
            try:
                item["sound"] = mixer.Sound(str(item["path"]))
            except Exception as e:
                print(f"Error cargando {item['path']}: {e}")
                self.next_track()
                return

        item["sound"].set_volume(item["volume"].get() / 100.0)
        loops = -1 if item["loop"].get() else 0
        self.current_channel = item["sound"].play(loops=loops)
        item["channel"] = self.current_channel

        self.current_song_label.config(text=f"▶ {item['path'].name}")

    def next_track(self):
        if not self.playing:
            return
        self.current_index += 1
        if self.current_index < len(self.playlist_items):
            self.play_current()
        else:
            self.playing = False
            self.current_channel = None
            self.current_song_label.config(text="")

    def next_track_manual(self):
        if not self.playing or not self.playlist_items:
            return
        if self.current_index < len(self.playlist_items) - 1:
            self.current_index += 1
            self.play_current()

    def previous_track(self):
        if not self.playing or not self.playlist_items:
            return
        if self.current_index > 0:
            self.current_index -= 1
            self.play_current()

    def check_playlist_end(self):
        if self.playing and self.current_channel:
            if not self.current_channel.get_busy():
                self.next_track()
        self.root.after(100, self.check_playlist_end)

    # ---------- FUNCIONES DEL TEMPORIZADOR ----------
    def format_time(self, seconds):
        mins, secs = divmod(seconds, 60)
        hours, mins = divmod(mins, 60)
        days, hours = divmod(hours, 24)
        if days > 0:
            return f"{days}d {hours:02}:{mins:02}:{secs:02}"
        elif hours > 0:
            return f"{hours:02}:{mins:02}:{secs:02}"
        else:
            return f"{mins:02}:{secs:02}"

    def start_timer(self):
        if not self.running:
            self.running = True
            self.paused = False
            self.update_timer()

    def update_timer(self):
        if self.running and not self.paused and self.remaining_seconds > 0:
            self.remaining_seconds -= 1
            self.label.config(text=self.format_time(self.remaining_seconds))
            self.root.after(1000, self.update_timer)
        elif self.remaining_seconds <= 0 and self.running:
            self.finish_timer()

    def pause_timer(self):
        self.paused = True

    def resume_timer(self):
        self.paused = False

    def reset_timer(self):
        self.running = False
        self.paused = False
        self.remaining_seconds = self.total_seconds
        self.label.config(text=self.format_time(self.remaining_seconds))

    def edit_time(self):
        self.running = False
        minutes = simpledialog.askinteger("Editar tiempo", "Ingrese minutos:", parent=self.root, minvalue=1)
        if minutes:
            self.total_seconds = minutes * 60
            self.remaining_seconds = self.total_seconds
            self.label.config(text=self.format_time(self.remaining_seconds))

    def finish_timer(self):
        mixer.music.load("finish.mp3")
        mixer.music.play(-1)

        modal = tk.Toplevel(self.root)
        modal.title("Tiempo terminado")
        modal.geometry("250x120")
        modal.attributes("-topmost", True)
        modal.grab_set()

        tk.Label(modal, text="¡El temporizador ha finalizado!", font=("Helvetica", 12)).pack(pady=15)
        tk.Button(modal, text="Aceptar", command=lambda: self.stop_sound(modal)).pack(pady=10)

        modal.protocol("WM_DELETE_WINDOW", lambda: self.stop_sound(modal))
        self.running = False

    def stop_sound(self, modal):
        mixer.music.stop()
        modal.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = TimerApp(root)
    root.mainloop()
