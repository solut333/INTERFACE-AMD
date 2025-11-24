import tkinter as tk
import sv_ttk
from tkinter import ttk, messagebox
from tkinter import font
from tkinter import filedialog
import json
import webbrowser
import os
import requests
from packaging.version import parse as parse_version
import queue
from collections import deque
import threading
from PIL import Image, ImageTk
import pystray

from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from hardware_controller import HardwareManager
from profile_manager import ProfileManager

class App(tk.Tk):
    __version__ = "1.0.0"
    PROJECT_URL = "https://github.com/solut333/INTERFACE-AMD"
    UPDATE_CHECK_URL = "https://gist.githubusercontent.com/solut333/48ed9af07f5cc27d801ff1d150e46c71/raw/version.json"

    def __init__(self):
        super().__init__()
        
        sv_ttk.set_theme("dark")
        self.attributes('-alpha', 0.0)
        
        self.title("Pop!_OS Hardware Controller")

        try:
            icon_image = ImageTk.PhotoImage(file="icon.png")
            self.iconphoto(True, icon_image)
        except tk.TclError:
            print("Aviso: Arquivo 'icon.png' não encontrado ou corrompido. Usando ícone padrão.")
            pass

        self.manager = HardwareManager()
        if not self.manager.controller:
            messagebox.showerror("Erro", "Nenhum hardware compatível encontrado. O programa será fechado.")
            self.destroy()
            return

        self.profile_manager = ProfileManager()
        self.min_power, self.max_power = self.manager.controller.get_power_limit_range()
        self.config_file = "config.json"
        self.settings = self.load_settings()

        saved_geometry = self.settings.get("window_geometry")
        if saved_geometry:
            self.geometry(saved_geometry)
        else:
            self.geometry("450x800")
        
        self.temp_data = deque(maxlen=30)
        self.log_queue = queue.Queue()
        self.all_logs = []
        self.log_filter_var = tk.StringVar()

        self.WARNING_TEMP = 75
        self.CRITICAL_TEMP = 85
        self.critical_alert_played = False

        self.start_minimized_var = tk.BooleanVar(value=self.settings.get("start_minimized", False))
        self.alert_sound_path = tk.StringVar(value=self.settings.get("alert_sound_path", "alert.wav"))
        self.current_profile_name = tk.StringVar(value="Padrão")
        
        self.create_widgets()
        self.update_ui_from_settings()
        self.update_stats()
        self.start_log_monitor()
        self.process_log_queue()

        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.setup_tray_icon()
        self.log_filter_var.trace_add("write", self.on_log_filter_change)

        self.create_menu()

        threading.Thread(target=self.check_for_updates, daemon=True).start()

        saved_tab_index = self.settings.get("active_tab", 0)
        if self.notebook:
            self.notebook.select(saved_tab_index)

        self._fade_in_animation(self)


    def create_widgets(self):
        top_level_frame = ttk.Frame(self, padding="10")
        top_level_frame.pack(fill="both", expand=True)

        notebook = ttk.Notebook(top_level_frame)
        notebook.pack(fill="both", expand=True, pady=(0, 10))

        self.notebook = notebook
        main_controls_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(main_controls_tab, text='Controle Principal')
        
        fan_label = ttk.Label(main_controls_tab, text="Velocidade da Ventoinha (%)")
        fan_label.pack(pady=(0, 5))
        self.fan_scale = ttk.Scale(main_controls_tab, from_=0, to=100, orient="horizontal", command=self.on_fan_change)
        self.fan_scale.pack(fill="x", expand=True)
        self.fan_value_label = ttk.Label(main_controls_tab, text="0%")
        self.fan_value_label.pack()

        core_clock_label = ttk.Label(main_controls_tab, text="Offset Clock do Núcleo (MHz)")
        core_clock_label.pack(pady=(10, 5))
        self.core_clock_entry = ttk.Entry(main_controls_tab)
        self.core_clock_entry.pack(fill="x", expand=True)

        mem_clock_label = ttk.Label(main_controls_tab, text="Offset Clock da Memória (MHz)")
        mem_clock_label.pack(pady=(10, 5))
        self.mem_clock_entry = ttk.Entry(main_controls_tab)
        self.mem_clock_entry.pack(fill="x", expand=True)

        power_label = ttk.Label(main_controls_tab, text="Limite de Energia (W)")
        power_label.pack(pady=(10, 5))
        self.power_scale = ttk.Scale(main_controls_tab, from_=self.min_power or 10, to=self.max_power or 100, orient="horizontal", command=self.on_power_change)
        self.power_scale.pack(fill="x", expand=True)
        self.power_value_label = ttk.Label(main_controls_tab, text="0W")
        self.power_value_label.pack()
        if not self.min_power or not self.max_power:
            self.power_scale.config(state="disabled")

        settings_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_tab, text='Configurações')

        log_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(log_tab, text='Logs do Sistema')
        log_filter_frame = ttk.Frame(log_tab)
        log_filter_frame.pack(fill="x", pady=(0, 5))
        ttk.Label(log_filter_frame, text="Filtrar:").pack(side="left", padx=(0, 5))
        filter_entry = ttk.Entry(log_filter_frame, textvariable=self.log_filter_var)
        filter_entry.pack(side="left", fill="x", expand=True)
        clear_button = ttk.Button(log_filter_frame, text="Limpar", command=lambda: self.log_filter_var.set(""))
        clear_button.pack(side="left", padx=(5, 0))
        log_text_frame = ttk.Frame(log_tab)
        log_text_frame.pack(fill="both", expand=True)
        self.log_text_widget = tk.Text(log_text_frame, state='disabled', wrap='word', height=10, background="#212121", foreground="white")
        scrollbar = ttk.Scrollbar(log_text_frame, command=self.log_text_widget.yview)
        self.log_text_widget['yscrollcommand'] = scrollbar.set
        scrollbar.pack(side="right", fill="y")
        self.log_text_widget.pack(side="left", fill="both", expand=True)
        self.log_text_widget.tag_config("error", foreground="#FF4C4C")
        self.log_text_widget.tag_config("warning", foreground="#FFA500") # Laranja
        self.log_text_widget.tag_config("notice", foreground="#FFFF00") # Amarelo
        self.log_text_widget.tag_config("info", foreground="#00bfff") # DeepSkyBlue para info geral

        profile_frame = ttk.LabelFrame(settings_tab, text="Perfis de Configuração")
        profile_frame.pack(fill="x", expand=True, pady=5)
        profile_select_frame = ttk.Frame(profile_frame)
        profile_select_frame.pack(fill="x", pady=5)
        ttk.Label(profile_select_frame, text="Selecionar Perfil:").pack(side="left", padx=5)
        self.profile_combobox = ttk.Combobox(profile_select_frame, state="readonly")
        self.profile_combobox.pack(side="left", expand=True, fill="x", padx=5)
        self.profile_combobox.bind("<<ComboboxSelected>>", self.load_profile_action)
        self.update_profile_dropdown()
        profile_save_frame = ttk.Frame(profile_frame)
        profile_save_frame.pack(fill="x", pady=5)
        ttk.Label(profile_save_frame, text="Nome do Perfil:").pack(side="left", padx=5)
        self.profile_name_entry = ttk.Entry(profile_save_frame)
        self.profile_name_entry.pack(side="left", expand=True, fill="x", padx=5)
        ttk.Button(profile_save_frame, text="Salvar", command=self.save_profile_action).pack(side="left", padx=5)
        ttk.Button(profile_save_frame, text="Excluir", command=self.delete_profile_action).pack(side="left", padx=5)

        general_settings_frame = ttk.LabelFrame(settings_tab, text="Configurações Gerais")
        general_settings_frame.pack(fill="x", expand=True, pady=5)
        alert_sound_frame = ttk.Frame(general_settings_frame, padding=5)
        alert_sound_frame.pack(fill="x")
        ttk.Label(alert_sound_frame, text="Som de Alerta:").pack(side="left", padx=(0, 5))
        sound_path_label = ttk.Label(alert_sound_frame, textvariable=self.alert_sound_path, relief="sunken", anchor="w")
        sound_path_label.pack(side="left", fill="x", expand=True)
        browse_button = ttk.Button(alert_sound_frame, text="Procurar...", command=self.select_alert_sound)
        browse_button.pack(side="left", padx=(5, 0))

        start_minimized_check = ttk.Checkbutton(general_settings_frame, text="Iniciar minimizado na bandeja do sistema", variable=self.start_minimized_var)
        start_minimized_check.pack(anchor="w", pady=5, padx=5)

        stats_frame = ttk.Frame(top_level_frame)
        stats_frame.pack(fill="x", expand=True)
        self.gpu_usage_label = ttk.Label(stats_frame, text="Uso da GPU: N/A")
        self.gpu_usage_label.pack(anchor="w")
        self.mem_usage_label = ttk.Label(stats_frame, text="Uso de Memória: N/A")
        self.mem_usage_label.pack(anchor="w")
        self.temp_label = ttk.Label(stats_frame, text="Temperatura: N/A")
        self.temp_label.pack(anchor="w")

        button_frame = ttk.Frame(top_level_frame)
        button_frame.pack(pady=20, fill="x", side="bottom")
        reset_button = ttk.Button(button_frame, text="Restaurar Padrão", command=self.reset_to_defaults)
        reset_button.pack(side="left", expand=True, padx=5)
        apply_button = ttk.Button(button_frame, text="Aplicar", command=self.apply_settings)
        apply_button.pack(side="left", expand=True, padx=5)
        save_button = ttk.Button(button_frame, text="Salvar e Aplicar", command=self.save_and_apply)
        save_button.pack(side="left", expand=True, padx=5)

        self.create_graph_widget(top_level_frame)

    def on_fan_change(self, value):
        val = int(float(value))
        self.fan_value_label.config(text=f"{val}%")

    def on_power_change(self, value):
        val = int(float(value))
        self.power_value_label.config(text=f"{val}W")

    def apply_settings(self):
        try:
            fan_speed = int(self.fan_scale.get())
            core_offset = int(self.core_clock_entry.get() or 0)
            mem_offset = int(self.mem_clock_entry.get() or 0)

            if self.power_scale["state"] != "disabled":
                power_limit = int(self.power_scale.get())
                self.manager.controller.set_power_limit(power_limit)

            self.manager.controller.set_fan_speed(fan_speed)
            self.manager.controller.set_core_clock_offset(core_offset)
            self.manager.controller.set_mem_clock_offset(mem_offset)
            
            messagebox.showinfo("Sucesso", "Configurações aplicadas!")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao aplicar configurações: {e}")

    def save_and_apply(self):
        self.settings = {
            "window_geometry": self.geometry(),
            "active_tab": self.notebook.index(self.notebook.select()),
            "fan_speed": int(self.fan_scale.get()),
            "core_clock_offset": int(self.core_clock_entry.get() or 0),
            "mem_clock_offset": int(self.mem_clock_entry.get() or 0),
            "alert_sound_path": self.alert_sound_path.get(),
            "start_minimized": self.start_minimized_var.get(),
            "power_limit": int(self.power_scale.get()) if self.power_scale["state"] != "disabled" else None,
        }
        with open(self.config_file, 'w') as f:
            json.dump(self.settings, f, indent=4)
        
        self.apply_settings()

    def reset_to_defaults(self):
        if messagebox.askyesno("Confirmar", "Tem certeza que deseja restaurar as configurações de fábrica?"):
            try:
                self.manager.controller.reset_settings()
                self.fan_scale.set(40)
                self.core_clock_entry.delete(0, tk.END)
                self.core_clock_entry.insert(0, "0")
                self.mem_clock_entry.delete(0, tk.END)
                self.mem_clock_entry.insert(0, "0")
                if self.power_scale["state"] != "disabled":
                    self.power_scale.set(self.max_power)
                messagebox.showinfo("Sucesso", "Configurações restauradas para o padrão de fábrica.")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao restaurar configurações: {e}")

    def get_current_ui_settings(self):
        return {
            "fan_speed": int(self.fan_scale.get()),
            "core_clock_offset": int(self.core_clock_entry.get() or 0),
            "mem_clock_offset": int(self.mem_clock_entry.get() or 0),
            "power_limit": int(self.power_scale.get()) if self.power_scale["state"] != "disabled" else None
        }

    def save_profile_action(self):
        profile_name = self.profile_name_entry.get().strip()
        if not profile_name:
            messagebox.showwarning("Aviso", "Por favor, insira um nome para o perfil.")
            return
        
        current_settings = self.get_current_ui_settings()
        try:
            self.profile_manager.save_profile(profile_name, current_settings)
            self.update_profile_dropdown()
            self.profile_combobox.set(profile_name)
            messagebox.showinfo("Sucesso", f"Perfil '{profile_name}' salvo com sucesso!")
        except ValueError as e:
            messagebox.showerror("Erro", str(e))
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao salvar perfil: {e}")

    def load_profile_action(self, event=None):
        profile_name = self.profile_combobox.get()
        if not profile_name:
            messagebox.showwarning("Aviso", "Por favor, selecione um perfil para carregar.")
            return
        
        settings = self.profile_manager.load_profile(profile_name)
        if settings:
            try:
                self.fan_scale.set(settings.get("fan_speed", 40))
                self.on_fan_change(self.fan_scale.get())
                self.core_clock_entry.delete(0, tk.END)
                self.core_clock_entry.insert(0, str(settings.get("core_clock_offset", 0)))
                self.mem_clock_entry.delete(0, tk.END)
                self.mem_clock_entry.insert(0, str(settings.get("mem_clock_offset", 0)))
                if self.power_scale["state"] != "disabled":
                    self.power_scale.set(settings.get("power_limit", self.max_power))
                    self.on_power_change(self.power_scale.get())
                self.apply_settings()
                messagebox.showinfo("Sucesso", f"Perfil '{profile_name}' carregado e aplicado!")
            except Exception as e:
                messagebox.showerror("Erro", f"Falha ao carregar e aplicar perfil: {e}")
        else:
            messagebox.showwarning("Aviso", f"Perfil '{profile_name}' não encontrado.")

    def delete_profile_action(self):
        profile_name = self.profile_combobox.get()
        if profile_name and messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir o perfil '{profile_name}'?"):
            if self.profile_manager.delete_profile(profile_name):
                self.update_profile_dropdown()
                messagebox.showinfo("Sucesso", f"Perfil '{profile_name}' excluído.")

    def load_settings(self):
        defaults = {"fan_speed": 40, "core_clock_offset": 0, "mem_clock_offset": 0, "power_limit": self.max_power, "alert_sound_path": "alert.wav", "start_minimized": False}
        try:
            if os.path.exists(self.config_file) and os.path.getsize(self.config_file) > 0:
                with open(self.config_file, 'r') as f:
                    defaults.update(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            print("Aviso: 'config.json' não encontrado ou corrompido. Usando configurações padrão.")
        return defaults

    def update_ui_from_settings(self):
        self.fan_scale.set(self.settings.get("fan_speed", 40))
        self.on_fan_change(self.fan_scale.get())
        self.core_clock_entry.insert(0, str(self.settings.get("core_clock_offset", 0)))
        self.mem_clock_entry.insert(0, str(self.settings.get("mem_clock_offset", 0)))
        self.alert_sound_path.set(self.settings.get("alert_sound_path", "alert.wav"))
        self.start_minimized_var.set(self.settings.get("start_minimized", False))

        if self.power_scale["state"] != "disabled":
            self.power_scale.set(self.settings.get("power_limit", self.max_power))
            self.on_power_change(self.power_scale.get())
        
        profile_names = self.profile_manager.get_profile_names()
        if profile_names:
            self.profile_combobox.set(profile_names[0])

        if self.start_minimized_var.get():
            self.withdraw()

    def update_stats(self):
        if self.manager.controller:
            gpu_usage = self.manager.controller.get_gpu_usage()
            mem_usage = self.manager.controller.get_memory_usage()
            temp = self.manager.controller.get_temperature()

            self.gpu_usage_label.config(text=f"Uso da GPU: {gpu_usage}")
            self.mem_usage_label.config(text=f"Uso de Memória: {mem_usage}")
            
            if temp is not None:
                self.temp_label.config(text=f"Temperatura: {temp:.1f}°C")
                if temp >= self.CRITICAL_TEMP:
                    if not self.critical_alert_played:
                        self.play_alert_sound()
                        self.critical_alert_played = True
                else:
                    self.critical_alert_played = False

                self.temp_data.append(temp)
                self.update_graph()
            else:
                self.temp_label.config(text="Temperatura: N/A")

        self.after(2000, self.update_stats)

    def play_alert_sound(self):
        sound_path = self.alert_sound_path.get()
        try:
            subprocess.Popen(["paplay", sound_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            print(f"Comando 'paplay' não encontrado. Não foi possível tocar o som de alerta.")
        except Exception as e:
            print(f"Erro ao tocar o som de alerta '{sound_path}': {e}")

    def select_alert_sound(self):
        filepath = filedialog.askopenfilename(
            title="Selecione o arquivo de som",
            filetypes=(("Arquivos de Áudio", "*.wav *.ogg"), ("Todos os arquivos", "*.*"))
        )
        if filepath:
            self.alert_sound_path.set(filepath)

    def create_graph_widget(self, parent_frame):
        self.fig = Figure(figsize=(5, 2.5), dpi=100, facecolor='#212121')
        self.fig.patch.set_facecolor('#212121')
        
        self.ax = self.fig.add_subplot(111)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent_frame)
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, pady=(10,0))
        self.canvas.get_tk_widget().config(bg='#212121')

    def update_graph(self):
        if not list(self.temp_data):
            return

        current_temp = self.temp_data[-1]
        plot_color = '#00bfff'
        if current_temp >= self.CRITICAL_TEMP:
            plot_color = 'red'
        elif current_temp >= self.WARNING_TEMP:
            plot_color = 'orange'

        self.ax.clear()
        self.ax.plot(list(self.temp_data), marker='o', linestyle='-', markersize=4, color=plot_color)

        self.ax.set_facecolor('#333333')
        self.ax.tick_params(axis='x', colors='white')
        self.ax.tick_params(axis='y', colors='white')
        self.ax.spines['bottom'].set_color('white')
        self.ax.spines['left'].set_color('white')
        self.ax.spines['top'].set_color('white')
        self.ax.spines['right'].set_color('white')

        title = self.ax.set_title("Histórico de Temperatura (°C)")
        title.set_color('white')
        self.ax.set_ylabel("Temp (°C)", color='white')
        self.ax.set_ylim(bottom=max(0, min(self.temp_data) - 10), top=max(100, max(self.temp_data) + 10))
        self.ax.grid(True)
        self.fig.tight_layout()
        self.canvas.draw()

    def update_profile_dropdown(self):
        profile_names = self.profile_manager.get_profile_names()
        self.profile_combobox['values'] = profile_names
        if profile_names:
            self.profile_combobox.set(profile_names[0])
        else:
            self.profile_combobox.set("")

    def setup_tray_icon(self):
        try:
            image = Image.open("icon.png")
        except FileNotFoundError:
            print("Erro: 'icon.png' não encontrado. Crie um ícone para a bandeja do sistema.")
            return

        menu = (pystray.MenuItem('Mostrar', self.show_window, default=True),
                pystray.MenuItem('Sair', self.quit_app))
        
        self.tray_icon = pystray.Icon("gpu_controller", image, "GPU Controller", menu)
        
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def show_window(self):
        self.deiconify()

    def hide_to_tray(self):
        self.withdraw()

    def quit_app(self):
        self.settings['active_tab'] = self.notebook.index(self.notebook.select())
        self.settings['window_geometry'] = self.geometry()
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Erro ao salvar a geometria da janela ao sair: {e}")

        self.tray_icon.stop()
        self._fade_out_animation(self)

    def check_for_updates(self):
        try:
            response = requests.get(self.UPDATE_CHECK_URL, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            latest_version = data.get("latest_version")
            download_url = data.get("download_url")

            if latest_version and download_url and parse_version(latest_version) > parse_version(self.__version__):
                if messagebox.askyesno("Atualização Automática Disponível", 
                                       f"Uma nova versão ({latest_version}) está disponível!\n"
                                       f"Você está usando a versão {self.__version__}.\n\n"
                                       "Deseja baixar e instalar agora? O aplicativo será reiniciado."):
                    self.run_auto_update(download_url)
        except Exception as e:
            print(f"Não foi possível verificar por atualizações: {e}")

    def run_auto_update(self, download_url):
        try:
            update_zip_path = "/tmp/gpu_controller_update.zip"
            print(f"Baixando atualização de {download_url}...")
            response = requests.get(download_url, stream=True)
            response.raise_for_status()
            with open(update_zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Download concluído.")

            updater_script_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "updater.py")
            install_dir = "/opt/pop-os-controller"

            print("Iniciando o processo de atualização...")
            subprocess.Popen(['python3', updater_script_path, update_zip_path, install_dir])

            self.quit_app()

        except Exception as e:
            messagebox.showerror("Erro na Atualização", f"Não foi possível baixar ou iniciar a atualização automática.\nErro: {e}")

    def create_menu(self):
        menubar = tk.Menu(self)
        
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Verificar Atualizações", command=self.check_for_updates)
        help_menu.add_command(label="Página do Projeto", command=lambda: webbrowser.open(self.PROJECT_URL))
        help_menu.add_separator()
        help_menu.add_command(label=f"Sobre (Versão {self.__version__})", command=self.show_about)
        
        menubar.add_cascade(label="Ajuda", menu=help_menu)
        self.config(menu=menubar)

    def show_about(self):
        about_win = tk.Toplevel(self)
        about_win.title("Sobre")
        about_win.transient(self)
        about_win.geometry("350x200")
        about_win.attributes('-alpha', 0.0)
        about_win.resizable(False, False)

        about_win.update_idletasks()
        width = about_win.winfo_width()
        height = about_win.winfo_height()
        x = (about_win.winfo_screenwidth() // 2) - (width // 2)
        y = (about_win.winfo_screenheight() // 2) - (height // 2)
        about_win.geometry(f'+{x}+{y}')

        main_frame = ttk.Frame(about_win, padding="10")
        main_frame.pack(fill="both", expand=True)

        try:
            logo_image = Image.open("logo.png")
            logo_image = logo_image.resize((64, 64), Image.Resampling.LANCZOS)
            logo_photo = ImageTk.PhotoImage(logo_image)
            
            logo_label = ttk.Label(main_frame, image=logo_photo)
            logo_label.image = logo_photo 
            logo_label.pack(pady=(0, 10))
        except FileNotFoundError:
            print("Aviso: Arquivo 'logo.png' não encontrado. A janela 'Sobre' será exibida sem o logo.")
            pass

        ttk.Label(main_frame, text="Pop!_OS Hardware Controller", font=("-size 12 -weight bold")).pack(pady=(0, 5))
        ttk.Label(main_frame, text=f"Versão {self.__version__}").pack()
        ttk.Label(main_frame, text="Um utilitário para monitorar e controlar sua GPU.").pack(pady=(0, 15))

        youtube_url = "https://www.youtube.com/@viruzinpriv2"
        link_font = font.Font(size=10, underline=True)
        youtube_label = ttk.Label(main_frame, text="Canal do Desenvolvedor", foreground="#00bfff", font=link_font, cursor="hand2")
        youtube_label.pack()
        youtube_label.bind("<Button-1>", lambda e: webbrowser.open(youtube_url))

        ttk.Button(main_frame, text="Fechar", command=lambda: self._fade_out_animation(about_win)).pack(pady=(20, 0))

        self._fade_in_animation(about_win)

    def _fade_in_animation(self, window, current_alpha=0.0):
        target_alpha = 0.95
        if current_alpha < target_alpha:
            current_alpha += 0.02
            window.attributes('-alpha', min(current_alpha, target_alpha))
            self.after(15, lambda: self._fade_in_animation(window, current_alpha))
        else:
            window.attributes('-alpha', target_alpha)

    def _fade_out_animation(self, window, current_alpha=None):
        if current_alpha is None:
            current_alpha = window.attributes('-alpha')

        if current_alpha > 0.0:
            current_alpha -= 0.05
            window.attributes('-alpha', max(current_alpha, 0.0))
            self.after(15, lambda: self._fade_out_animation(window, current_alpha))
        else:
            window.destroy()

    def start_log_monitor(self):
        thread = threading.Thread(target=self._log_reader_thread, daemon=True)
        thread.start()

    def _log_reader_thread(self):
        try:
            process = subprocess.Popen(
                ['journalctl', '-f', '-p', '7', '--no-pager'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8'
            )
            for line in iter(process.stdout.readline, ''):
                self.log_queue.put(line)
        except FileNotFoundError:
            self.log_queue.put("ERRO: O comando 'journalctl' não foi encontrado. A aba de logs não funcionará.\n")
        except Exception as e:
            self.log_queue.put(f"ERRO ao iniciar o monitor de logs: {e}\n")

    def process_log_queue(self):
        while not self.log_queue.empty():
            line = self.log_queue.get_nowait()
            self.all_logs.append(line)
            
            filter_text = self.log_filter_var.get().lower()
            if not filter_text or filter_text in line.lower():
                self._insert_log_line_with_color(line)
                
        self.after(100, self.process_log_queue)

    def on_log_filter_change(self, *args):
        filter_text = self.log_filter_var.get().lower()

        self.log_text_widget.config(state='normal')
        self.log_text_widget.delete('1.0', 'end')

        for line in self.all_logs:
            if not filter_text or filter_text in line.lower():
                self._insert_log_line_with_color(line)

        self.log_text_widget.see('end')
        self.log_text_widget.config(state='disabled')

    def _insert_log_line_with_color(self, line):
        self.log_text_widget.config(state='normal')

        line_lower = line.lower()
        tag_to_apply = None

        if "error" in line_lower or "failed" in line_lower:
            tag_to_apply = "error"
        elif "warning" in line_lower:
            tag_to_apply = "warning"
        elif "notice" in line_lower:
            tag_to_apply = "notice"
        elif "info" in line_lower:
            tag_to_apply = "info"

        self.log_text_widget.insert('end', line, tag_to_apply)
        self.log_text_widget.config(state='disabled')
