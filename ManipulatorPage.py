import os
import time

import cv2
import tkinter as tk
from tkinter import ttk
import numpy as np
from PIL import ImageTk, Image


def is_convertible_to_int(element):
    try:
        int(element)
        return True
    except (ValueError, TypeError):
        return False


class ManipulatorPage(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.cap = None
        self.video_paused = False
        self.update_flag = False
        self.controller = controller
        self.font = cv2.FONT_HERSHEY_SIMPLEX

        self.image_shape = [int(1200 * self.controller.scale_factor),
                            int(840 * self.controller.scale_factor)]
        self.center_x = self.image_shape[0] // 2
        self.center_y = self.image_shape[1] // 2

        self.min_area = 250
        self.objects_coord = []
        self.kernelOpen = np.ones((5, 5))
        self.kernelClose = np.ones((20, 20))
        self.lowerBound = np.array([0, 0, 0], dtype=np.uint8)
        self.upperBound = np.array([179, 255, 255], dtype=np.uint8)

        self.color_dict = {
            'blue': (105, 219, 129),
            'orange': (11, 252, 176),
            'yellow': (19, 255, 169),
            'green': (77, 225, 77)
        }

        self.exposure = 0
        self.white_balance = 0

        self.create_widgets()
        self.set_camera_config()

    def create_widgets(self):
        paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        camera_frame = tk.Frame(paned_window)
        paned_window.add(camera_frame, weight=7)

        settings_frame = ttk.Frame(paned_window)
        paned_window.add(settings_frame, weight=2)

        label_settings = ttk.Label(settings_frame, text="Настройки", background="#001f4b", foreground='white',
                                   font=("Arial", int(30 * self.controller.scale_factor)))
        label_settings.pack(pady=10)

        stop_icon = ImageTk.PhotoImage(
            Image.open("images_data/stop_icon.png").resize((int(50 * self.controller.scale_factor),
                                                            int(50 * self.controller.scale_factor))))
        pause_icon = ImageTk.PhotoImage(
            Image.open("images_data/pause_icon.png").resize((int(50 * self.controller.scale_factor),
                                                             int(50 * self.controller.scale_factor))))

        button_frame = tk.Frame(settings_frame, bg='#001f4b')
        button_frame.pack(pady=10)

        self.pause_button = tk.Button(button_frame, image=pause_icon, command=self.pause_action,
                                      borderwidth=0)
        self.pause_button.image = pause_icon
        self.pause_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = tk.Button(button_frame, image=stop_icon,
                                     command=lambda: self.controller.show_frame("HomePage"),
                                     borderwidth=0)
        self.stop_button.image = stop_icon
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.cam_label = tk.Label(camera_frame, bg='#001f4b')
        self.cam_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.cam_label.bind("<Button-1>", self.pick_color)

        self.create_management_widgets(settings_frame)

    def create_slider(self, frame, text, from_, to_, command, row, default=0):
        style = ttk.Style()
        style.configure("Custom.Horizontal.TScale",
                        troughcolor='#001f4b',
                        background='#001f4b',
                        sliderthickness=int(20 * self.controller.scale_factor))

        # Настройка метки (текст смещен к левой границе)
        label = ttk.Label(frame, text=f"{text}",
                          font=("Arial", int(20 * self.controller.scale_factor)),
                          background="#001f4b",
                          foreground="white")
        label.place(x=10, y=15 * self.controller.scale_factor + row * 50, anchor='w')

        # Получаем ширину родительского фрейма
        frame.update_idletasks()  # Обновляем информацию о размерах фрейма
        frame_width = frame.winfo_width()

        # Настройка ползунка (ползунок смещен к правой границе)
        slider = ttk.Scale(frame, from_=from_, to=to_, orient="horizontal", command=command,
                           style="Custom.Horizontal.TScale")
        slider.set(default)

        # Ползунок выравниваем по правой стороне с учетом ширины фрейма
        slider_width = int(200 * self.controller.scale_factor)
        slider_x = frame_width - slider_width - 10
        slider.place(x=slider_x, y=row * 50, width=slider_width)

        return slider

    def create_management_widgets(self, frame):
        # Создаем settings_color_frame с фиксированным размером
        settings_color_frame = ttk.Frame(frame, width=400, height=350)
        settings_color_frame.place(x=50, y=150)

        # Добавляем отступы для управления положением
        self.create_slider(settings_color_frame, "Экспозиция", -180, 180, self.update_exposure, row=2)
        self.create_slider(settings_color_frame, "Баланс белого", -180, 180, self.update_white_balance, row=3)

        self.sliders = {}
        self.sliders["Красный"] = self.create_slider(settings_color_frame, "Красный", -255, 255,
                                                     self.update_color_components, row=4)
        self.sliders["Зеленый"] = self.create_slider(settings_color_frame, "Зеленый", -255, 255,
                                                     self.update_color_components, row=5)
        self.sliders["Синий"] = self.create_slider(settings_color_frame, "Синий", -255, 255,
                                                   self.update_color_components, row=6)

    def update_exposure(self, value):
        self.exposure = int(float(value))

    def update_white_balance(self, value):
        self.white_balance = int(float(value))

    def update_color_components(self, value):
        pass

    def apply_settings(self, frame):
        # Применение настроек контраста и яркости (экспозиция)
        frame = cv2.convertScaleAbs(frame, alpha=1, beta=self.exposure)

        # Баланс белого (коррекция LAB)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(frame)
        l = cv2.add(l, self.white_balance)
        frame = cv2.merge([l, a, b])
        frame = cv2.cvtColor(frame, cv2.COLOR_LAB2BGR)

        red_value = int(self.sliders["Красный"].get())
        green_value = int(self.sliders["Зеленый"].get())
        blue_value = int(self.sliders["Синий"].get())

        b, g, r = cv2.split(frame)
        b = cv2.add(b, blue_value)
        g = cv2.add(g, green_value)
        r = cv2.add(r, red_value)
        frame = cv2.merge([b, g, r])

        return frame

    def set_camera_config(self):
        if not os.path.exists("config.txt"):
            self.k_x = 83 / 70
            self.k_y = 83 / 70
            self.mm_to_pixel_x = int(250 * self.k_x)
            self.mm_to_pixel_y = int(250 * self.k_x)
            self.x_0, self.y_0 = self.mm_to_pixel_x, self.mm_to_pixel_y
            self.x_max = self.x_0 + self.mm_to_pixel_x
            self.y_max = self.y_0 + self.mm_to_pixel_y
            self.h = 70
            self.len_f_x, self.len_f_y = 500, 500
        else:
            with open("config.txt", "r") as file:
                config_data = {line.split()[0]: float(line.split()[1]) for line in file}
                self.k_x = float(config_data['k_x'])
                self.k_y = float(config_data['k_y'])
                self.len_f_x, self.len_f_y = int(config_data['len_f_x']), int(config_data['len_f_y'])
                self.x_0, self.y_0 = int(self.k_x * self.len_f_x // 2), int(self.k_y * self.len_f_y // 2)
                self.x_max = self.x_0 * 2
                self.y_max = self.y_0 * 2
                self.h = int(config_data['h'])

    def pick_color(self, event, color=None):
        if self.controller.current_frame == self and self.cap is not None and not self.video_paused:
            x, y = 0, 0
            if event is not None:
                x, y = event.x, event.y
            image_width, image_height = self.image_shape

            if 0 <= x < image_width and 0 <= y < image_height:
                frame_x = int((x / image_width) * self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                frame_y = int((y / image_height) * self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                _, frame = self.cap.read()
                if frame is not None:
                    frame = self.apply_settings(frame)
                    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

                    if event is not None:
                        hsv_value = hsv_frame[frame_y, frame_x]
                    else:
                        hsv_value = self.color_dict[color]

                    h_val = int(hsv_value[0])
                    s_val = int(hsv_value[1])
                    v_val = int(hsv_value[2])

                    tol_h = 2
                    tol_s = 50
                    tol_v = 50

                    self.lowerBound = np.array([
                        max(h_val - tol_h, 0),
                        max(s_val - tol_s, 0),
                        max(v_val - tol_v, 0)
                    ], dtype=np.uint8)
                    self.upperBound = np.array([
                        min(h_val + tol_h, 179),
                        min(s_val + tol_s, 255),
                        min(v_val + tol_v, 255)
                    ], dtype=np.uint8)

    def pause_action(self):
        self.video_paused = not self.video_paused

    def update_stream(self):
        if not self.video_paused:
            ret, frame = self.cap.read()
            if ret:
                frame = self.apply_settings(frame)
                frame = cv2.resize(frame, self.image_shape)
                imgHSV = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                mask = cv2.inRange(imgHSV, self.lowerBound, self.upperBound)
                maskOpen = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernelOpen)
                maskClose = cv2.morphologyEx(maskOpen, cv2.MORPH_CLOSE, self.kernelClose)
                maskFinal = maskClose
                conts, _ = cv2.findContours(maskFinal.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

                self.objects_coord = []
                for i, contour in enumerate(conts):
                    x, y, w, h = cv2.boundingRect(contour)
                    center_x, center_y = x + w // 2, self.image_shape[1] - (y + h) + h // 2
                    center_x_cam, center_y_cam = center_x - self.image_shape[0] // 2, center_y - self.image_shape[1] // 2
                    center_x_coord, center_y_coord = center_x_cam + self.x_0, center_y_cam + self.y_0
                    if w * h > self.min_area and 0 <= center_x_coord <= self.x_max and 0 <= center_y_coord <= self.y_max:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                        self.objects_coord.append(
                            (int(center_x_coord * 1 / self.k_x),
                             int(center_y_coord * 1 / self.k_y)))
                        print(self.objects_coord)

                line_length = 20
                cv2.line(frame,
                         (self.center_x - line_length // 2, self.center_y),
                         (self.center_x + line_length // 2, self.center_y),
                         (255, 0, 0), 1)
                cv2.line(frame, (self.center_x, self.center_y - line_length // 2),
                         (self.center_x, self.center_y + line_length // 2),
                         (255, 0, 0), 1)

                # Draw axis
                image_width, image_height = self.image_shape
                padding = 35
                axis_length = min(image_width, image_height) // 6

                origin_x = padding
                origin_y = image_height - padding
                cv2.arrowedLine(
                    frame,
                    (origin_x, origin_y),  # Начало вектора
                    (origin_x, origin_y - axis_length),  # Конец вектора
                    (255, 0, 0),  # Цвет (синий)
                    3,  # Толщина линии
                    tipLength=0.15  # Длина наконечника стрелки
                )
                cv2.putText(frame, "Y", (origin_x - 15, origin_y - axis_length), self.font, 0.5,
                            (255, 0, 0), 2)
                cv2.putText(frame, f"{self.len_f_y}, mm", (origin_x + 10, origin_y - axis_length),
                            self.font, 0.43, (255, 0, 0), 1)

                cv2.arrowedLine(
                    frame,
                    (origin_x, origin_y),
                    (origin_x + axis_length, origin_y),
                    (0, 0, 255),
                    3,
                    tipLength=0.15
                )
                cv2.putText(frame, "X", (origin_x + axis_length - 5, origin_y + 20), self.font, 0.5,
                            (0, 0, 255), 2)
                cv2.putText(frame, f"{self.len_f_x}, mm", (origin_x + axis_length - 30, origin_y - 20), self.font,
                            0.43, (0, 0, 255), 1)

                img = Image.fromarray(frame)
                imgtk = ImageTk.PhotoImage(image=img)
                self.cam_label.imgtk = imgtk
                self.cam_label.config(image=imgtk)

        if self.update_flag:
            self.cam_label.after(10, self.update_stream)

    def send_coords(self, number=1):
        if len(self.objects_coord) == 0:
            self.controller.ser.send_command("There are no suitable objects\n")
            return
        if number > len(self.objects_coord):
            self.controller.ser.send_command("Out of range\n")
            return
        object = sorted(self.objects_coord, key=lambda point: point[0] ** 2 + point[1] ** 2)[number - 1]
        self.controller.ser.send_command(
            f"G01 X {object[0]} Y {object[1]} Z {self.h}\n"
        )

    def response_to_request(self, received_list):
        if len(received_list) != 2 or len(received_list) != 3 or received_list[0].lower() != 'get':
            self.controller.ser.send_command("An error in the command.\n")
            return

        if self.controller.current_frame != self:
            self.controller.show_frame("ManipulatorPage")

        if len(received_list) == 2:
            if not is_convertible_to_int(received_list[1]):
                self.controller.ser.send_command("An error in the command.\n")
                return
            number = int(received_list[1])
            self.send_coords(number)
            return

        if len(received_list) == 3:
            if not is_convertible_to_int(received_list[2]):
                self.controller.ser.send_command("An error in the command.\n")
                return
            if received_list[1].lower() not in self.color_dict:
                self.controller.ser.send_command("Unknown color.\n")
                return
            self.pick_color(None, received_list[1])
            time.sleep(0.3)
            number = int(received_list[2])
            self.send_coords(number)
            return


