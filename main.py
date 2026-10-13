from flask import Flask, render_template, request, jsonify
import subprocess
import json
import re
import os
# Gw pakai model AI dari openrouter btw :v
# Sebagai tempat untuk menjalankan AI nya (karena gak bisa secara langsung) gw pakai Pi
# Kalau kalian belum login Pi, kalian bisa login dulu, login pakai openrouter dan masukkan API KEY
app = Flask(__name__)
MODEL = "openrouter/thinkingmachines/inkling-small:free"
def ask_ai(prompt):
    command = [
        "pi",
        "--model", MODEL,
        "--no-session",
        "--no-tools",
        "--system-prompt",
        (
            "Kamu adalah AI pembuat dan penilai soal SMP. "
            "Ikuti instruksi dengan tepat. Jika diminta JSON, "
            "hasilkan JSON valid tanpa teks tambahan."
        ),
        "-p",
        prompt
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=180
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("AI terlalu lama merespons.")
    except FileNotFoundError:
        raise RuntimeError(
            "Perintah pi tidak ditemukan. "
            "Pastikan Pi terinstal dan tersedia di PATH Flask."
        )
    if result.returncode != 0:
        error = result.stderr.strip()
        raise RuntimeError(
            "Pi gagal menjalankan AI: " + (error or "Error tidak diketahui.")
        )
    content = result.stdout.strip()
    content = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        content,
        flags=re.IGNORECASE
    )
    content = re.sub(r"\s*```\s*$", "", content)
    decoder = json.JSONDecoder()
    for index, char in enumerate(content):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(content[index:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    raise RuntimeError(
        "AI tidak menghasilkan objek JSON yang valid."
    )
def get_request_data():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return None
    return data
@app.route("/")
def index():
    return render_template("index.html")
@app.route("/generate", methods=["POST"])
def generate():
    data = get_request_data()
    if data is None:
        return jsonify({
            "error": "Request harus menggunakan JSON yang valid."
        }), 400
    mapel = str(data.get("mapel", "")).strip()
    kelas = str(data.get("kelas", "")).strip()
    bab = str(data.get("bab", "")).strip()
    kesulitan = str(
        data.get("kesulitan", "Sedang")
    ).strip()
    if not mapel or not kelas or not bab:
        return jsonify({
            "error": "Data soal belum lengkap."
        }), 400
    prompt = f"""
Kamu adalah guru SMP yang membuat soal ujian.

Mata pelajaran: {mapel}
Kelas: {kelas}
Materi: {bab}
Kesulitan: {kesulitan}

Buat TEPAT 10 soal pilihan ganda yang sesuai
dengan mata pelajaran dan materi tersebut.

Setiap soal harus memiliki:
- Pertanyaan yang jelas.
- Empat pilihan A, B, C, D.
- Tepat satu jawaban benar.
- Kunci jawaban.
- Pembahasan.

Jangan mencampurkan materi dari mata pelajaran lain.
Jangan mengulang pertanyaan.

Gunakan format JSON berikut:

{{
    "questions": [
        {{
            "question": "Pertanyaan",
            "options": {{
                "A": "Pilihan A",
                "B": "Pilihan B",
                "C": "Pilihan C",
                "D": "Pilihan D"
            }},
            "answer": "A",
            "explanation": "Pembahasan"
        }}
    ]
}}

Harus ada tepat 10 soal.
Saat memberi soal harus cepat, jangan lama-lama.
Nilai answer hanya boleh A, B, C, atau D.
Jangan memberikan teks di luar JSON.
"""
    try:
        soal = ask_ai(prompt)
        questions = soal.get("questions")
        if not isinstance(questions, list) or len(questions) != 10:
            raise RuntimeError(
                "AI tidak menghasilkan tepat 10 soal."
            )
        for nomor, item in enumerate(questions, start=1):
            if not isinstance(item, dict):
                raise RuntimeError(
                    f"Format soal nomor {nomor} tidak valid."
                )
            options = item.get("options")
            if not isinstance(options, dict):
                raise RuntimeError(
                    f"Pilihan soal nomor {nomor} tidak valid."
                )
            if not all(
                isinstance(options.get(huruf), str)
                and options[huruf].strip()
                for huruf in ("A", "B", "C", "D")
            ):
                raise RuntimeError(
                    f"Soal nomor {nomor} harus memiliki "
                    "empat pilihan lengkap."
                )
            if not isinstance(item.get("question"), str):
                raise RuntimeError(
                    f"Pertanyaan nomor {nomor} tidak valid."
                )
            if item.get("answer") not in ("A", "B", "C", "D"):
                raise RuntimeError(
                    f"Kunci jawaban nomor {nomor} tidak valid."
                )
            if not isinstance(item.get("explanation"), str):
                raise RuntimeError(
                    f"Pembahasan nomor {nomor} tidak valid."
                )
        return jsonify({"questions": questions})
    except Exception as e:
        app.logger.exception("Gagal membuat soal")
        return jsonify({
            "error": str(e)
        }), 500
@app.route("/finish", methods=["POST"])
def finish():
    data = get_request_data()
    if data is None:
        return jsonify({
            "error": "Request harus menggunakan JSON yang valid."
        }), 400
    questions = data.get("questions")
    user_answers = data.get("answers")
    if not isinstance(questions, list) or len(questions) != 10:
        return jsonify({
            "error": "Soal harus berjumlah 10."
        }), 400
    if not isinstance(user_answers, list) or len(user_answers) != 10:
        return jsonify({
            "error": "Jawaban siswa harus berjumlah 10."
        }), 400
    for item in questions:
        if (
            not isinstance(item, dict)
            or item.get("answer") not in ("A", "B", "C", "D")
        ):
            return jsonify({
                "error": "Data kunci jawaban tidak valid."
            }), 400
    normalized_answers = []
    for answer in user_answers:
        if answer is None or answer == "":
            normalized_answers.append("Tidak dijawab")
        elif answer in ("A", "B", "C", "D"):
            normalized_answers.append(answer)
        else:
            return jsonify({
                "error": "Ada jawaban siswa yang tidak valid."
            }), 400
    prompt = f"""
Kamu adalah guru SMP yang menilai ujian.

Soal beserta kunci jawaban:
{json.dumps(questions, ensure_ascii=False)}

Jawaban siswa sesuai urutan soal:
{json.dumps(normalized_answers, ensure_ascii=False)}

Tugas:
1. Periksa setiap jawaban berdasarkan kunci jawaban.
2. Tentukan benar atau salah secara akurat.
3. Berikan pembahasan untuk setiap soal.
4. Berikan komentar singkat tentang hasil siswa.

Jangan mengubah kunci jawaban yang tersedia.

Kembalikan JSON dengan format:

{{
    "correct": 0,
    "wrong": 0,
    "score": 0,
    "comment": "Komentar singkat",
    "details": [
        {{
            "number": 1,
            "user_answer": "A",
            "correct_answer": "B",
            "correct": false,
            "explanation": "Pembahasan"
        }}
    ]
}}

Harus ada tepat 10 details.
correct adalah jumlah jawaban benar.
wrong adalah jumlah jawaban salah atau tidak dijawab.
score adalah jumlah benar dikali 10.
correct pada setiap detail harus berupa boolean.
Jangan memberikan teks di luar JSON.
"""
    try:
        result = ask_ai(prompt)
        details = result.get("details")
        if not isinstance(details, list) or len(details) != 10:
            raise RuntimeError(
                "AI tidak menghasilkan tepat 10 detail penilaian."
            )
        correct_count = 0
        for index, detail in enumerate(details):
            if not isinstance(detail, dict):
                raise RuntimeError(
                    f"Detail penilaian nomor {index + 1} tidak valid."
                )
            expected = questions[index]["answer"]
            given = normalized_answers[index]
            is_correct = given == expected
            if is_correct:
                correct_count += 1
            detail["number"] = index + 1
            detail["user_answer"] = given
            detail["correct_answer"] = expected
            detail["correct"] = is_correct
            if not isinstance(detail.get("explanation"), str):
                detail["explanation"] = questions[index].get(
                    "explanation", ""
                )
        result["correct"] = correct_count
        result["wrong"] = 10 - correct_count
        result["score"] = correct_count * 10
        result["details"] = details
        if not isinstance(result.get("comment"), str):
            result["comment"] = "Penilaian selesai."
        return jsonify(result)
    except Exception as e:
        app.logger.exception("Gagal menilai jawaban")
        return jsonify({
            "error": str(e)
        }), 500
@app.route("/quiz")
def quiz():
    return render_template("quiz.html")
@app.route("/result")
def result():
    return render_template("result.html")
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=6767,
        debug=os.getenv("FLASK_DEBUG") == "1"
    )
