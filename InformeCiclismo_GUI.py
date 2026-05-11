import tkinter as tk
from tkinter import filedialog
from load_data import load_data

class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Excel Plotter")
        self.geometry("900x600")

        # Store file paths
        self.file1 = None
        self.file2 = None

        # Container for pages
        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)

        # Dict to keep pages
        self.frames = {}

        for Page in (StartPage, PlotPage):
            page_name = Page.__name__
            frame = Page(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame("StartPage")

    def show_frame(self, page_name):
        """Raise a page to the front"""
        frame = self.frames[page_name]
        frame.tkraise()


class StartPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        label = tk.Label(self, text="Upload 2 Excel files", font=("Arial", 16))
        label.pack(pady=20)

        btn1 = tk.Button(self, text="Load File 1", command=self.load_file1)
        btn1.pack(pady=5)

        btn2 = tk.Button(self, text="Load File 2", command=self.load_file2)
        btn2.pack(pady=5)

        self.next_btn = tk.Button(self, text="Go to Plots",
                                  command=lambda: controller.show_frame("PlotPage"),
                                  state=tk.DISABLED)
        self.next_btn.pack(pady=20)

    def load_file1(self):
        self.controller.file1 = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        self.check_ready()

    def load_file2(self):
        self.controller.file2 = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        self.check_ready()

    def check_ready(self):
    # Check if both file paths have been selected
     if self.controller.file1 and self.controller.file2:
        # 1. Disable the button *temporarily* while processing (optional, but good practice)
        self.next_btn.config(state=tk.DISABLED) 
        
        # 2. Automatically process the data as soon as both files are selected
        self.process_data()
            
    def process_data(self):
        # Call your load_data function with the selected file paths
        data1, peaks1 = load_data(self.controller.file1)
        data2, peaks2 = load_data(self.controller.file2)
        self.controller.data1 = data1
        self.controller.peaks1 = peaks1
        self.controller.data2 = data2
        self.controller.peaks2 = peaks2
        
        if self.controller.data1 is not None and self.controller.data2 is not None:
            self.next_btn.config(state=tk.NORMAL)
        else:
        # Handle error case (optional)
            print("Error: Data processing failed.")


class PlotPage(tk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller

        label = tk.Label(self, text="Plots Page", font=("Arial", 16))
        label.pack(pady=10)

        # Create 2 empty windows for future plots
        frame1 = tk.Frame(self, width=400, height=400, bg="lightgray")
        frame1.pack(side="left", expand=True, fill="both", padx=10, pady=10)

        frame2 = tk.Frame(self, width=400, height=400, bg="lightblue")
        frame2.pack(side="right", expand=True, fill="both", padx=10, pady=10)

        # Back button
        back_btn = tk.Button(self, text="Back",
                             command=lambda: controller.show_frame("StartPage"))
        back_btn.pack(pady=10, side="bottom")


if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
