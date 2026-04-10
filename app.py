import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageDraw, ImageFont, ImageTk
import calendar

# ステータスの定数定義
STATUS_NONE = 0      # なし
STATUS_BUSINESS = 1  # 丸 (営業日)
STATUS_HOLIDAY = 2   # バツ (休み)

# --- ：カラーパレット（視認性とデザイン性の両立） ---
COLOR_ACCENT = "#E07A5F"     # テラコッタレッド（温かみのある営業日カラー）
COLOR_HOLIDAY = "#81B29A"    # セージグリーン（目に優しい休日カラー、青より今風）
COLOR_TEXT_MAIN = "#3D405B"  # ネイビーグレー（真っ黒ではなく、洗練された印象に）
COLOR_TEXT_SUB = "#9CA3AF"   # ソフトグレー
COLOR_GRID_LINE = "#E5E7EB"  # 罫線の色（真っ黒ではなく薄いグレーにして抜け感を出す）

class CalendarApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("カレンダー生成ツール v4.1 (誤操作防止版)")
        self.geometry("1400x900")

        # --- 変数定義 ---
        self.year_var = tk.IntVar(value=2025)
        self.month_var = tk.IntVar(value=12)
        self.bg_path_var = tk.StringVar()
        
        # 日付ごとの情報を管理する辞書
        # day_statuses: { 1: STATUS_BUSINESS, ... }
        self.day_statuses = {} 
        # day_texts: { 1: {"text": "WS", "color": "#d65f5f"}, ... }
        self.day_texts = {}
        
        # 最後にクリックされた日付 (編集用)
        self.selected_day = tk.IntVar(value=0)
        self.selected_day_text = tk.StringVar()
        
        # 全体テキスト（自由配置）リスト
        # [{"text": "営業時間...", "x": 0.5, "y": 0.2, "size": 30, "color": "#000"}, ...]
        self.free_texts = []
        # 編集中のフリーテキストインデックス
        self.editing_text_index = -1
        self.free_text_input = tk.StringVar()
        
        # 座標関連
        self.start_x = tk.DoubleVar(value=100.0)
        self.start_y = tk.DoubleVar(value=300.0)
        self.step_x = tk.DoubleVar(value=120.0)
        self.step_y = tk.DoubleVar(value=100.0)
        
        self.pil_image = None
        self.tk_image = None
        self.scale_factor = 1.0
        
        # スライダーの参照保持用
        self.scale_start_x = None
        self.scale_start_y = None
        self.scale_step_x = None
        self.scale_step_y = None
        
        self.create_layout()
        self.reset_statuses()

    def create_layout(self):
        # 左パネルをスクロール可能にするためのコンテナ
        container_left = ttk.Frame(self, width=400, relief="ridge")
        container_left.pack(side="left", fill="y")
        
        canvas_left = tk.Canvas(container_left, width=380)
        scrollbar_left = ttk.Scrollbar(container_left, orient="vertical", command=canvas_left.yview)
        self.frame_left = ttk.Frame(canvas_left)
        
        self.frame_left.bind(
            "<Configure>",
            lambda e: canvas_left.configure(scrollregion=canvas_left.bbox("all"))
        )
        canvas_left.create_window((0, 0), window=self.frame_left, anchor="nw")
        canvas_left.configure(yscrollcommand=scrollbar_left.set)
        
        canvas_left.pack(side="left", fill="both", expand=True)
        scrollbar_left.pack(side="right", fill="y")

        # 右側プレビューエリア
        frame_right = ttk.Frame(self, relief="sunken")
        frame_right.pack(side="right", fill="both", expand=True)

        # --- 左側の部品配置 ---
        pad_opts = {'fill': 'x', 'pady': 5, 'padx': 5}

        # 1. 画像
        group_file = ttk.LabelFrame(self.frame_left, text="1. 背景画像")
        group_file.pack(**pad_opts)
        ttk.Button(group_file, text="画像を開く...", command=self.load_image).pack(**pad_opts)

        # 2. 年月
        group_date = ttk.LabelFrame(self.frame_left, text="2. 年月")
        group_date.pack(**pad_opts)
        f_date = ttk.Frame(group_date)
        f_date.pack()
        ttk.Entry(f_date, textvariable=self.year_var, width=6).pack(side="left")
        ttk.Label(f_date, text="年").pack(side="left")
        ttk.Entry(f_date, textvariable=self.month_var, width=4).pack(side="left")
        ttk.Label(f_date, text="月").pack(side="left")
        ttk.Button(group_date, text="更新 / リセット", command=self.reset_and_update).pack(fill="x", pady=2)

        # 3. 日付ごとの編集（新機能）
        group_day_edit = ttk.LabelFrame(self.frame_left, text="3. 日付の編集 (文字入れ)")
        group_day_edit.pack(**pad_opts)
        
        f_sel_day = ttk.Frame(group_day_edit)
        f_sel_day.pack(fill="x")
        ttk.Label(f_sel_day, text="選択中の日付:").pack(side="left")
        ttk.Label(f_sel_day, textvariable=self.selected_day, font=("", 12, "bold"), foreground="red").pack(side="left", padx=5)
        ttk.Label(f_sel_day, text="※プレビューをクリックして選択", font=("", 8), foreground="gray").pack(side="left")
        
        ttk.Label(group_day_edit, text="追加文字 (WS, cafeなど):").pack(anchor="w")
        entry_day_text = ttk.Entry(group_day_edit, textvariable=self.selected_day_text)
        entry_day_text.pack(fill="x")
        # Enterキーで反映
        entry_day_text.bind("<Return>", lambda e: self.apply_day_text())
        
        f_btns = ttk.Frame(group_day_edit)
        f_btns.pack(fill="x", pady=2)
        ttk.Button(f_btns, text="文字を反映", command=self.apply_day_text).pack(side="left", expand=True, fill="x")
        ttk.Button(f_btns, text="☕", width=3, command=lambda: self.insert_icon("☕")).pack(side="left")
        ttk.Button(f_btns, text="🍰", width=3, command=lambda: self.insert_icon("🍰")).pack(side="left")
        
        # 4. 全体文字（新機能）
        group_free_text = ttk.LabelFrame(self.frame_left, text="4. 自由テキスト (営業時間など)")
        group_free_text.pack(**pad_opts)
        ttk.Label(group_free_text, text="内容:").pack(anchor="w")
        entry_free = ttk.Entry(group_free_text, textvariable=self.free_text_input)
        entry_free.pack(fill="x")
        
        f_free_btns = ttk.Frame(group_free_text)
        f_free_btns.pack(fill="x", pady=2)
        ttk.Button(f_free_btns, text="＋ 追加/更新", command=self.add_or_update_free_text).pack(side="left", expand=True, fill="x")
        ttk.Button(f_free_btns, text="削除", command=self.delete_free_text).pack(side="left")
        
        ttk.Label(group_free_text, text="※追加後、プレビュー上でクリックして移動", font=("", 8), foreground="gray").pack()

        # 5. 位置調整
        group_pos = ttk.LabelFrame(self.frame_left, text="5. レイアウト調整")
        group_pos.pack(**pad_opts)
        
        # --- ここから修正: マウス移動を廃止する代わりにスライダーで調整できるようにする ---
        ttk.Label(group_pos, text="開始位置 X (横):").pack(anchor="w")
        self.scale_start_x = ttk.Scale(group_pos, variable=self.start_x, from_=0, to=1000, command=self.update_preview)
        self.scale_start_x.pack(fill="x")
        
        ttk.Label(group_pos, text="開始位置 Y (縦):").pack(anchor="w")
        self.scale_start_y = ttk.Scale(group_pos, variable=self.start_y, from_=0, to=1000, command=self.update_preview)
        self.scale_start_y.pack(fill="x")
        
        ttk.Separator(group_pos, orient="horizontal").pack(fill="x", pady=5)

        ttk.Label(group_pos, text="マスの大きさ:").pack(anchor="w")
        self.scale_step_x = ttk.Scale(group_pos, variable=self.step_x, from_=10, to=500, command=self.update_preview)
        self.scale_step_x.pack(fill="x")
        
        ttk.Label(group_pos, text="行の間隔:").pack(anchor="w")
        self.scale_step_y = ttk.Scale(group_pos, variable=self.step_y, from_=10, to=500, command=self.update_preview)
        self.scale_step_y.pack(fill="x")

        # 6. 一括設定
        group_tools = ttk.LabelFrame(self.frame_left, text="6. 便利ツール")
        group_tools.pack(**pad_opts)
        ttk.Button(group_tools, text="土日を「休み(×)」にする", command=self.set_weekends_holiday).pack(fill="x", pady=2)
        ttk.Button(group_tools, text="全てリセット", command=self.reset_statuses).pack(fill="x", pady=2)

        # 保存
        ttk.Button(self.frame_left, text="画像を保存する", command=self.save_image).pack(**pad_opts, ipady=10)

        # --- 右側キャンバス ---
        self.canvas = tk.Canvas(frame_right, bg="gray", cursor="cross")
        v_scroll = ttk.Scrollbar(frame_right, orient="vertical", command=self.canvas.yview)
        h_scroll = ttk.Scrollbar(frame_right, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        v_scroll.pack(side="right", fill="y")
        h_scroll.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)

    # --- ロジック ---

    def insert_icon(self, icon_char):
        current = self.selected_day_text.get()
        self.selected_day_text.set(current + icon_char)

    def apply_day_text(self):
        day = self.selected_day.get()
        text = self.selected_day_text.get()
        if day == 0: return
        
        if text.strip() == "":
            if day in self.day_texts: del self.day_texts[day]
        else:
            self.day_texts[day] = {"text": text, "color": COLOR_ACCENT}
        self.update_preview()

    def add_or_update_free_text(self):
        text = self.free_text_input.get()
        if not text: return
        
        if self.editing_text_index >= 0:
            # 更新
            self.free_texts[self.editing_text_index]["text"] = text
            self.editing_text_index = -1 # 編集終了
            self.free_text_input.set("")
        else:
            # 新規追加 (デフォルト位置は中央上部)
            if self.pil_image:
                w, h = self.pil_image.size
                self.free_texts.append({
                    "text": text,
                    "x": w / 2, # 画像上の絶対座標
                    "y": h * 0.2,
                    "color": "#333333"
                })
            else:
                self.free_texts.append({"text": text, "x": 100, "y": 100, "color": "#333333"})
            self.free_text_input.set("")
            
        self.update_preview()

    def delete_free_text(self):
        if self.editing_text_index >= 0:
            del self.free_texts[self.editing_text_index]
            self.editing_text_index = -1
            self.free_text_input.set("")
            self.update_preview()

    # --- 共通: 白枠(カード) ---
    def apply_white_card(self, img_pil):
        width, height = img_pil.size
        overlay = Image.new("RGBA", img_pil.size, (255, 255, 255, 0))
        draw_overlay = ImageDraw.Draw(overlay)
        
        card_w = width * 0.85
        card_h = height * 0.8 # 少し縦長に
        
        card_x1 = (width - card_w) / 2
        card_y1 = (height - card_h) / 2
        card_x2 = card_x1 + card_w
        card_y2 = card_y1 + card_h
        
        draw_overlay.rounded_rectangle(
            (card_x1, card_y1, card_x2, card_y2),
            radius=int(width * 0.05),
            fill=(255, 255, 255, 235) 
        )
        return Image.alpha_composite(img_pil, overlay)

    def reset_and_update(self):
        self.reset_statuses()
        self.day_texts = {} # テキストもリセット
        self.free_texts = []
        self.update_preview()

    def reset_statuses(self):
        self.day_statuses = {}
        cal = calendar.Calendar()
        for day in cal.itermonthdays(self.year_var.get(), self.month_var.get()):
            if day != 0:
                self.day_statuses[day] = STATUS_NONE
        self.update_preview()

    def set_weekends_holiday(self):
        year, month = self.year_var.get(), self.month_var.get()
        cal = calendar.Calendar(firstweekday=6) 
        month_matrix = cal.monthdayscalendar(year, month)
        for week in month_matrix:
            if week[0] != 0: self.day_statuses[week[0]] = STATUS_HOLIDAY
            if week[6] != 0: self.day_statuses[week[6]] = STATUS_HOLIDAY
        self.update_preview()

    def load_image(self):
        file_path = filedialog.askopenfilename(filetypes=[("Image Files", "*.jpg;*.png;*.jpeg")])
        if not file_path: return
        self.bg_path_var.set(file_path)
        
        self.pil_image = Image.open(file_path).convert("RGBA")
        width, height = self.pil_image.size
        
        new_step_x = width * 0.11
        new_step_y = new_step_x * 1.1 # 文字を入れる分、縦の間隔を広げる
        
        self.step_x.set(new_step_x)
        self.step_y.set(new_step_y)
        
        # スライダーの上限更新
        max_step = width * 0.4
        self.scale_step_x.configure(to=max_step)
        self.scale_step_y.configure(to=max_step)
        
        # 位置スライダーの上限も画像サイズに合わせる
        self.scale_start_x.configure(to=width)
        self.scale_start_y.configure(to=height)

        cal_total_width = new_step_x * 7
        center_x = (width - cal_total_width) / 2
        self.start_x.set(center_x)
        self.start_y.set(height * 0.40) 

        # プレビュー縮小
        preview_max_w = 900
        preview_max_h = 700
        scale_w = preview_max_w / width
        scale_h = preview_max_h / height
        self.scale_factor = min(1.0, scale_w, scale_h) 
        
        new_w = int(width * self.scale_factor)
        new_h = int(height * self.scale_factor)
        
        img_with_card = self.apply_white_card(self.pil_image.copy())
        img_resized = img_with_card.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        self.tk_image = ImageTk.PhotoImage(img_resized)
        
        self.canvas.config(scrollregion=(0, 0, new_w, new_h))
        self.canvas.create_image(0, 0, image=self.tk_image, anchor="nw")
        
        self.update_preview()
        messagebox.showinfo("読み込み完了", "レイアウト調整完了。")

    def on_canvas_click(self, event):
        if not self.pil_image: return
        
        click_x = self.canvas.canvasx(event.x)
        click_y = self.canvas.canvasy(event.y)
        
        real_click_x = click_x / self.scale_factor
        real_click_y = click_y / self.scale_factor
        
        # --- 自由テキストの選択判定 ---
        hit_text_index = -1
        min_dist = 50.0 # 判定距離
        for i, ft in enumerate(self.free_texts):
            dist = ((ft["x"] - real_click_x)**2 + (ft["y"] - real_click_y)**2)**0.5
            if dist < min_dist:
                hit_text_index = i
                break
        
        if hit_text_index >= 0:
            self.editing_text_index = hit_text_index
            self.free_text_input.set(self.free_texts[i]["text"])
            self.selected_day.set(0) # 日付選択解除
            self.update_preview()
            return # テキスト選択優先

        # --- カレンダー日付の判定 ---
        year, month = self.year_var.get(), self.month_var.get()
        sx, sy = self.start_x.get(), self.start_y.get()
        stx, sty = self.step_x.get(), self.step_y.get()
        
        cal = calendar.Calendar(firstweekday=6)
        days = cal.monthdayscalendar(year, month)
        
        hit_day = None
        
        for row_idx, week in enumerate(days):
            for col_idx, day in enumerate(week):
                if day == 0: continue
                day_x = sx + (col_idx * stx)
                day_y = sy + (row_idx * sty)
                
                if (day_x <= real_click_x <= day_x + stx) and (day_y <= real_click_y <= day_y + sty):
                    hit_day = day
                    break
            if hit_day: break
            
        if hit_day:
            self.editing_text_index = -1 # 自由テキスト選択解除
            
            # 同じ日付を連続クリック -> ステータス変更
            if self.selected_day.get() == hit_day:
                current_status = self.day_statuses.get(hit_day, STATUS_NONE)
                self.day_statuses[hit_day] = (current_status + 1) % 3
            
            # 日付選択状態にする
            self.selected_day.set(hit_day)
            # 既存のテキストがあれば入力欄に入れる
            if hit_day in self.day_texts:
                self.selected_day_text.set(self.day_texts[hit_day]["text"])
            else:
                self.selected_day_text.set("")
                
            self.update_preview()
        else:
            # 何もないところ -> 選択解除のみ (位置移動はしない！)
            self.editing_text_index = -1
            self.selected_day.set(0)
            # self.start_x.set(real_click_x) <-- 削除
            # self.start_y.set(real_click_y) <-- 削除
            self.update_preview()

    def on_canvas_drag(self, event):
        if not self.pil_image: return
        # 自由テキストをドラッグ移動
        if self.editing_text_index >= 0:
            click_x = self.canvas.canvasx(event.x)
            click_y = self.canvas.canvasy(event.y)
            real_x = click_x / self.scale_factor
            real_y = click_y / self.scale_factor
            
            self.free_texts[self.editing_text_index]["x"] = real_x
            self.free_texts[self.editing_text_index]["y"] = real_y
            self.update_preview()

    def get_fonts(self, width):
        # 画像サイズに応じたフォントサイズ
        size_title = int(width * 0.08)
        size_week = int(width * 0.035)
        size_date = int(width * 0.045)
        size_small = int(width * 0.025) # WSなどの文字
        size_free = int(width * 0.035)  # 自由テキスト

        # ★重要: おしゃれフォントの優先順位
        # Windows標準でセリフ体(明朝系)を探す
        fonts = {}
        
        def load_font(name_list, size):
            for name in name_list:
                try:
                    return ImageFont.truetype(name, size)
                except:
                    continue
            return ImageFont.load_default()

        # 1. 英語・数字用 (Times New Romanなど)
        fonts["en_title"] = load_font(["times.ttf", "georgia.ttf", "arial.ttf"], size_title)
        fonts["en_date"]  = load_font(["times.ttf", "georgia.ttf", "arial.ttf"], size_date)
        
        # 2. 日本語用 (游明朝, MS明朝など)
        fonts["jp_week"]  = load_font(["yumin.ttf", "msmincho.ttc", "msgothic.ttc"], size_week)
        fonts["jp_small"] = load_font(["yumin.ttf", "msmincho.ttc", "msgothic.ttc"], size_small)
        fonts["jp_free"]  = load_font(["yumin.ttf", "msmincho.ttc", "msgothic.ttc"], size_free)
        
        return fonts

    def update_preview(self, event=None):
        if not self.pil_image: return
        self.canvas.delete("guide")
        
        # プレビュー倍率
        sf = self.scale_factor
        
        # カレンダー設定
        year, month = self.year_var.get(), self.month_var.get()
        sx = self.start_x.get() * sf
        sy = self.start_y.get() * sf
        stx = self.step_x.get() * sf
        sty = self.step_y.get() * sf
        
        img_w = self.tk_image.width()
        
        cal = calendar.Calendar(firstweekday=6)
        days = cal.monthdayscalendar(year, month)

        # --- ガイド描画 ---
        
        # 1. タイトル (プレビュー用簡易表示)
        title_y = sy - (sty * 2.5)
        self.canvas.create_text(img_w/2, title_y, text=f"{year}  {month}", font=("Times New Roman", 20, "bold"), fill=COLOR_TEXT_MAIN, tags="guide")

        # 2. 自由テキスト
        for i, ft in enumerate(self.free_texts):
            fx = ft["x"] * sf
            fy = ft["y"] * sf
            color = "red" if i == self.editing_text_index else COLOR_TEXT_MAIN
            self.canvas.create_text(fx, fy, text=ft["text"], fill=color, font=("Yu Mincho", 12), tags="guide")
            if i == self.editing_text_index:
                self.canvas.create_rectangle(fx-5, fy-5, fx+5, fy+5, outline="red", tags="guide")

        # 3. カレンダー本体
        header_y = sy - (sty * 0.8)
        weekdays = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] # 英語表記でおしゃれに
        jp_weekdays = ["日", "月", "火", "水", "木", "金", "土"] # どっちがいいかはお好みで
        
        for i, w in enumerate(jp_weekdays):
            wx = sx + (i * stx)
            c = COLOR_ACCENT if i == 0 else COLOR_TEXT_SUB
            self.canvas.create_text(wx + stx/2, header_y, text=w, fill=c, font=("Yu Mincho", 10), tags="guide")

        for row_idx, week in enumerate(days):
            for col_idx, day in enumerate(week):
                x = sx + (col_idx * stx)
                y = sy + (row_idx * sty)
                
                if day != 0:
                    status = self.day_statuses.get(day, STATUS_NONE)
                    day_txt_info = self.day_texts.get(day, None)
                    
                    # 選択中ガイド
                    if self.selected_day.get() == day:
                        self.canvas.create_rectangle(x, y, x+stx, y+sty, outline="orange", width=2, tags="guide")
                    
                    # ステータス
                    if status == STATUS_BUSINESS: 
                        self.canvas.create_oval(x+5, y+5, x+stx-5, y+sty-15, outline=COLOR_ACCENT, width=1.5, tags="guide")
                    elif status == STATUS_HOLIDAY: 
                        self.canvas.create_line(x+10, y+10, x+stx-10, y+sty-20, fill=COLOR_HOLIDAY, width=1.5, tags="guide")
                        self.canvas.create_line(x+stx-10, y+10, x+10, y+sty-20, fill=COLOR_HOLIDAY, width=1.5, tags="guide")

                    # 日付数字 (Times系をイメージ)
                    self.canvas.create_text(x+stx/2, y+sty/3, text=str(day), fill=COLOR_TEXT_MAIN, font=("Times New Roman", 14), tags="guide")
                    
                    # 追加文字 (WSなど)
                    if day_txt_info:
                        self.canvas.create_text(x+stx/2, y+sty*0.75, text=day_txt_info["text"], fill=COLOR_ACCENT, font=("Yu Mincho", 8), tags="guide")

    def save_image(self):
        if not self.pil_image: return
        
        save_path = filedialog.asksaveasfilename(defaultextension=".png", initialfile=f"{self.year_var.get()}_{self.month_var.get()}.png")
        if not save_path: return

        img_out = self.pil_image.copy().convert("RGBA")
        img_out = self.apply_white_card(img_out)
        
        width, height = img_out.size
        draw = ImageDraw.Draw(img_out)
        
        fonts = self.get_fonts(width)
        
        sx, sy = self.start_x.get(), self.start_y.get()
        stx, sty = self.step_x.get(), self.step_y.get()
        line_width = max(1, int(width * 0.002))

        # 1. 自由テキスト描画
        for ft in self.free_texts:
            # 中央寄せで描画
            bbox = draw.textbbox((0, 0), ft["text"], font=fonts["jp_free"])
            w = bbox[2] - bbox[0]
            draw.text((ft["x"] - w/2, ft["y"]), ft["text"], fill=ft["color"], font=fonts["jp_free"])

        # 2. タイトル描画
        title_y = sy - (sty * 2.5)
        title_text = f"{self.year_var.get()}   {self.month_var.get()}"
        bbox = draw.textbbox((0, 0), title_text, font=fonts["en_title"])
        title_w = bbox[2] - bbox[0]
        draw.text(((width - title_w) / 2, title_y), title_text, fill=COLOR_TEXT_MAIN, font=fonts["en_title"])

        # 3. 曜日
        weekdays = ["日", "月", "火", "水", "木", "金", "土"]
        header_y = sy - (sty * 0.8)
        
        for i, w in enumerate(weekdays):
            wx = sx + (i * stx)
            bbox = draw.textbbox((0, 0), w, font=fonts["jp_week"])
            w_w = bbox[2] - bbox[0]
            c = COLOR_ACCENT if i == 0 else COLOR_TEXT_SUB
            draw.text((wx + (stx - w_w)/2, header_y), w, fill=c, font=fonts["jp_week"])

        # 4. カレンダー
        cal = calendar.Calendar(firstweekday=6)
        days = cal.monthdayscalendar(self.year_var.get(), self.month_var.get())

        for row_idx, week in enumerate(days):
            for col_idx, day in enumerate(week):
                if day == 0: continue
                
                x = sx + (col_idx * stx)
                y = sy + (row_idx * sty)
                
                center_x = x + stx / 2
                
                # ステータス
                status = self.day_statuses.get(day, STATUS_NONE)
                padding = stx * 0.15
                
                # ステータス図形の高さを少し調整（文字が入るため）
                oval_bottom = y + sty * 0.7 
                
                if status == STATUS_HOLIDAY: 
                    m = stx * 0.25
                    draw.line((x+m, y+m, x+stx-m, oval_bottom-m), fill=COLOR_HOLIDAY, width=line_width)
                    draw.line((x+m, oval_bottom-m, x+stx-m, y+m), fill=COLOR_HOLIDAY, width=line_width)
                    
                elif status == STATUS_BUSINESS: 
                    draw.ellipse(
                        (x+padding, y+padding, x+stx-padding, oval_bottom-padding),
                        outline=COLOR_ACCENT, width=line_width
                    )

                # 日付 (Times系)
                bbox = draw.textbbox((0, 0), str(day), font=fonts["en_date"])
                d_w = bbox[2] - bbox[0]
                d_h = bbox[3] - bbox[1]
                # 少し上に配置
                draw.text((center_x - d_w/2, y + sty*0.15), str(day), fill=COLOR_TEXT_MAIN, font=fonts["en_date"])

                # 追加文字 (WSなど)
                day_txt_info = self.day_texts.get(day, None)
                if day_txt_info:
                    txt = day_txt_info["text"]
                    bbox = draw.textbbox((0, 0), txt, font=fonts["jp_small"])
                    t_w = bbox[2] - bbox[0]
                    # 日付の下に配置
                    draw.text((center_x - t_w/2, y + sty*0.65), txt, fill=day_txt_info["color"], font=fonts["jp_small"])

        img_out.save(save_path)
        messagebox.showinfo("完了", "保存しました！")

if __name__ == "__main__":
    app = CalendarApp()
    app.mainloop()