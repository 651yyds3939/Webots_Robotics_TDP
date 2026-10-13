import queue
from pathlib import Path
from threading import Thread, Lock
from ultralytics import YOLO
import time

import cv2
import numpy as np
import csv
from Utils.CourseSpecs import BALL_DIAMETER

class ImageServer:
    def __init__(self, width, height, camera, robot_name, position, display=False):
        self.camera = camera  # camera
        self.width = width
        self.height = height
        self.robot_name = robot_name
        self.position = position
        self.display = display
        self._latest = None
        self._lock = Lock()
        self.running = True
        model_path = Path(__file__).resolve().with_name("best.pt")
        self.model = YOLO(str(model_path), verbose=False)
        self.queue = queue.Queue(maxsize=3)
        self.data_buffer = []
        self.ball_diameter = BALL_DIAMETER
        self.horizontal_fov = np.rad2deg(camera.getFov())
        self.focal_length = width / (2 * np.tan(camera.getFov() / 2))
        self.vertical_fov = np.rad2deg(2 * np.arctan(height / (2 * self.focal_length)))
        self.log_path = Path(__file__).resolve().parent / "vision_logs" / (
            f"data_{robot_name}_{position}_{time.time_ns()}.csv"
        )
        # Start only after all state needed by the worker has been initialized.
        self.thread = Thread(target=self.run, daemon=True)
        self.thread.start()

    def send(self, image, capture=None):
        if not self.running:
            return
        # Keep recent observations without blocking the simulation on inference.
        try:
            self.queue.put_nowait((image, capture))
        except queue.Full:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except queue.Empty:
                pass
            try:
                self.queue.put_nowait((image, capture))
            except queue.Full:
                pass

    def stop(self):
        self.running = False
        self.thread.join(timeout=5)

    def latest(self):
        with self._lock:
            return self._latest

    def ball_distance(self, ball_width):
        """Approximate optical-axis depth from ball bounding-box width.

        This is not robot-to-ball ground distance: camera pose and detection
        error still require calibration and validation.
        """
        if ball_width <= 0:
            raise ValueError("Ball width must be positive")
        distance = self.ball_diameter * self.focal_length / ball_width
        self.data_buffer.append({
            "timestamp": time.time(), "distance_estimate": distance
        })
        return distance

    def ball_heading(self, ball_center_x, ball_center_y):
        """Camera-relative horizontal bearing, positive to the image right."""
        angle = np.arctan2(ball_center_x - self.width / 2, self.focal_length)
        self.data_buffer.append({
            "timestamp": time.time(), "angle_estimate": np.rad2deg(angle)
        })
        return np.rad2deg(angle)

    def run(self):
        while self.running:
            try:
                img, capture = self.queue.get(timeout=0.1)
                cvimg = np.frombuffer(img, dtype=np.uint8).reshape((self.height, self.width, 4))
                
                frame = cv2.cvtColor(cvimg, cv2.COLOR_BGRA2BGR)
                # if self.position == "Bottom":
                if self.position in ("Top", "Bottom"):
                    results = self.model.predict(frame,verbose=False)[0]
                    threshold = 0.5
                    
                    best = None
                    for result in results.boxes.data.tolist():
                        x1, y1, x2, y2, score, class_id = result

                        if score > threshold:
                            if results.names[int(class_id)] == 'Ball':
                                ball_width = x2 - x1
                                ball_height = y2 - y1
                                ball_center_x = (x1 + x2) / 2
                                ball_center_y = (y1 + y2) / 2
                                self.ball_distance(ball_width)
                                self.ball_heading(ball_center_x, ball_center_y)   
                                if capture is not None and (best is None or score > best["confidence"]):
                                    best = {"capture": capture, "confidence": score,
                                            "depth": self.ball_diameter*self.focal_length/ball_width,
                                            "bearing": float(np.arctan2(ball_center_x-self.width/2, self.focal_length)),
                                            "elevation_down": float(np.arctan2(ball_center_y-self.height/2, self.focal_length))}
                                self.data_buffer.append({
                                        'timestamp': time.time(),
                                        'ball_width': ball_width,
                                        'ball_height': ball_height,
                                        'x1': x1,
                                        'y1': y1,
                                        'x2': x2,
                                        'y2': y2,
                                        'score': score
                                    })
                                


                            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 4)
                            cv2.putText(frame, results.names[int(class_id)].upper(), (int(x1), int(y1 - 10)),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 255, 0), 3, cv2.LINE_AA)
                
                    with self._lock:
                        self._latest = best
                    if self.display:
                        cv2.imshow(f'{self.robot_name} {self.position}',frame)
                        cv2.waitKey(1)
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as error:
                self.running = False
                print(f"Vision error ({self.robot_name}/{self.position}): {error}")
            finally:
                self.save_data_to_csv()

    def save_data_to_csv(self):
        """Saves the collected data points into a CSV file"""
        if self.data_buffer:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            fieldnames = (
                "timestamp", "distance_estimate", "angle_estimate", "ball_width",
                "ball_height", "x1", "y1", "x2", "y2", "score"
            )
            write_header = not self.log_path.exists()
            with self.log_path.open("a", newline="") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if write_header:
                    writer.writeheader()
                writer.writerows(self.data_buffer)
            self.data_buffer = []
