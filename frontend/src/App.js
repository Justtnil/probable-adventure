import React, { useEffect, useMemo, useState } from "react";
import "./App.css";
import axios from "axios";
import { format, startOfMonth, endOfMonth, subDays } from "date-fns";
import { DayPicker, Day } from "react-day-picker";
import "react-day-picker/dist/style.css";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const defaultRanges = [
  { key: "7", label: "Last 7 days", calc: () => ({ start: format(subDays(new Date(), 6), "yyyy-MM-dd"), end: format(new Date(), "yyyy-MM-dd") }) },
  { key: "30", label: "Last 30 days", calc: () => ({ start: format(subDays(new Date(), 29), "yyyy-MM-dd"), end: format(new Date(), "yyyy-MM-dd") }) },
  { key: "m", label: "This month", calc: () => ({ start: format(startOfMonth(new Date()), "yyyy-MM-dd"), end: format(endOfMonth(new Date()), "yyyy-MM-dd") }) },
];

function App() {
  const [moods, setMoods] = useState([]);
  const [entries, setEntries] = useState([]);
  const [byDate, setByDate] = useState({});
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [selectedMood, setSelectedMood] = useState(null);
  const [note, setNote] = useState("");
  const [rangeKey, setRangeKey] = useState("30");
  const [showCustomize, setShowCustomize] = useState(false);

  const dateStr = useMemo(() => format(selectedDate, "yyyy-MM-dd"), [selectedDate]);

  const colorMap = useMemo(() => {
    const map = {};
    moods.forEach((m) => (map[m.value] = m.color || "#999999"));
    return map;
  }, [moods]);

  const loadMoods = async () => {
    try {
      const cfg = await axios.get(`${API}/moods/config`);
      setMoods(cfg.data.moods);
    } catch (e) {
      const def = await axios.get(`${API}/moods/defaults`);
      setMoods(def.data);
    }
  };

  const loadEntries = async (start, end) => {
    try {
      const res = await axios.get(`${API}/entries`, { params: { start, end } });
      setEntries(res.data);
      const map = {};
      res.data.forEach((e) => (map[e.date] = e));
      setByDate(map);
      // If selected date has entry, prefill
      if (map[dateStr]) {
        setSelectedMood(map[dateStr].mood_value);
        setNote(map[dateStr].note || "");
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    loadMoods();
    const { start, end } = defaultRanges.find((r) => r.key === rangeKey).calc();
    loadEntries(start, end);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSelectDay = (day) => {
    if (!day) return;
    setSelectedDate(day);
    const ds = format(day, "yyyy-MM-dd");
    const e = byDate[ds];
    setSelectedMood(e ? e.mood_value : null);
    setNote(e ? e.note || "" : "");
  };

  const saveEntry = async () => {
    if (!selectedMood) return;
    const mood = moods.find((m) => m.value === selectedMood);
    try {
      const payload = {
        date: dateStr,
        mood_value: selectedMood,
        emoji: mood?.emoji || "",
        note,
      };
      const res = await axios.post(`${API}/entries`, payload);
      const newEntry = res.data;
      const updated = entries.filter((e) => e.date !== newEntry.date).concat([newEntry]).sort((a, b) => a.date.localeCompare(b.date));
      setEntries(updated);
      const map = {};
      updated.forEach((e) => (map[e.date] = e));
      setByDate(map);
    } catch (e) {
      console.error(e);
      alert("Failed to save entry");
    }
  };

  const exportPdf = async () => {
    try {
      const { start, end } = defaultRanges.find((r) => r.key === rangeKey).calc();
      const res = await axios.get(`${API}/export/pdf`, { params: { start, end }, responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/pdf" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `mood_report_${start}_${end}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error(e);
      alert("Failed to export PDF");
    }
  };

  const toggleCustomize = () => setShowCustomize((s) => !s);

  const saveMoods = async () => {
    try {
      const payload = { moods };
      await axios.post(`${API}/moods/config`, payload);
      alert("Mood set saved!");
      setShowCustomize(false);
    } catch (e) {
      console.error(e);
      alert("Failed to save moods");
    }
  };

  const addMood = () => {
    setMoods((prev) => prev.concat([{ value: `mood_${prev.length + 1}`, emoji: "😊", label: "New", color: "#9ca3af" }]));
  };

  const updateMoodField = (idx, field, value) => {
    setMoods((prev) => prev.map((m, i) => (i === idx ? { ...m, [field]: value } : m)));
  };

  // DayPicker modifiers for entries
  const modifiers = useMemo(() => {
    return {
      hasEntry: (day) => !!byDate[format(day, "yyyy-MM-dd")],
    };
  }, [byDate]);

  const modifiersStyles = useMemo(() => {
    // Color day background by mood color
    const styles = {};
    Object.keys(byDate).forEach((d) => {
      const entry = byDate[d];
      const key = `day-${d}`;
      styles[key] = { backgroundColor: colorMap[entry.mood_value] || "#e5e7eb", color: "#111827", borderRadius: 8 };
    });
    return styles;
  }, [byDate, colorMap]);

  const DayContent = (props) => {
    const day = props?.date instanceof Date ? props.date : new Date(props?.date);
    if (Number.isNaN(day?.getTime())) {
      return <div className="w-full h-full flex items-center justify-center text-xs text-gray-400">?</div>;
    }
    const ds = format(day, "yyyy-MM-dd");
    const entry = byDate[ds];
    return (
      <div className="w-full h-full flex flex-col items-center justify-center">
        <div className="text-sm">{day.getDate()}</div>
        {entry ? <div className="text-lg leading-none">{entry.emoji}</div> : null}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-rose-50 to-indigo-50 text-gray-800">
      <div className="max-w-6xl mx-auto px-4 py-6">
        <header className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="text-3xl">📝</div>
            <h1 className="text-2xl sm:text-3xl font-bold">Daily Feels</h1>
          </div>
          <div className="flex items-center gap-2">
            <select
              className="px-3 py-2 rounded-md bg-white border shadow-sm"
              value={rangeKey}
              onChange={(e) => {
                const v = e.target.value; setRangeKey(v);
                const { start, end } = defaultRanges.find((r) => r.key === v).calc();
                loadEntries(start, end);
              }}
            >
              {defaultRanges.map((r) => (
                <option key={r.key} value={r.key}>{r.label}</option>
              ))}
            </select>
            <button onClick={exportPdf} className="px-3 py-2 rounded-md bg-indigo-600 text-white shadow hover:bg-indigo-500">Export PDF</button>
            <button onClick={toggleCustomize} className="px-3 py-2 rounded-md bg-gray-800 text-white shadow hover:bg-gray-700">Customize Moods</button>
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-6">
          {/* Calendar */}
          <div className="lg:col-span-2 bg-white rounded-xl shadow p-4">
            <h2 className="font-semibold text-lg mb-2">Your Month</h2>
            <DayPicker
              mode="single"
              selected={selectedDate}
              onSelect={onSelectDay}
              showOutsideDays
              className="rdp"
              components={{ Day: DayContent }}
              styles={{ caption: { fontWeight: 600 }, day: { borderRadius: 8 }, head_cell: { fontWeight: 600 }, nav_button: { color: '#111827' } }}
            />
          </div>

          {/* Entry panel */}
          <div className="bg-white rounded-xl shadow p-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-lg">{format(selectedDate, "eeee, MMM d")}</h2>
              {byDate[dateStr] ? <span className="text-xs px-2 py-1 rounded-full bg-green-100 text-green-700">Saved</span> : null}
            </div>

            <div className="mt-3 grid grid-cols-6 gap-2">
              {moods.map((m) => (
                <button
                  key={m.value}
                  onClick={() => setSelectedMood(m.value)}
                  className={`group flex flex-col items-center justify-center gap-1 px-2 py-2 rounded-lg border hover:shadow ${selectedMood === m.value ? 'bg-indigo-50 border-indigo-300' : 'bg-white'}`}
                  title={m.label}
                >
                  <span className="text-2xl">{m.emoji}</span>
                  <span className="text-[10px] text-gray-600">{m.label}</span>
                </button>
              ))}
            </div>

            <div className="mt-4">
              <textarea
                placeholder="Add a note (optional)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="w-full min-h-[100px] rounded-lg border p-3 focus:outline-none focus:ring-2 focus:ring-indigo-400"
              />
            </div>

            <button onClick={saveEntry} disabled={!selectedMood} className="mt-3 w-full px-4 py-2 rounded-lg bg-indigo-600 text-white font-medium shadow hover:bg-indigo-500 disabled:opacity-50">Save</button>
          </div>
        </div>

        {/* History */}
        <div className="bg-white rounded-xl shadow p-4 mt-6">
          <h2 className="font-semibold text-lg mb-2">Recent Entries</h2>
          <div className="divide-y">
            {entries.length === 0 && <div className="text-sm text-gray-500 py-6">No entries yet. Pick a mood and save your first entry!</div>}
            {entries.slice(-14).reverse().map((e) => (
              <div key={e.id} className="py-3 flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="text-2xl">{e.emoji}</div>
                  <div>
                    <div className="font-medium">{e.date}</div>
                    {e.note ? <div className="text-sm text-gray-600 max-w-3xl">{e.note}</div> : null}
                  </div>
                </div>
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: colorMap[e.mood_value] || '#9ca3af' }}></div>
              </div>
            ))}
          </div>
        </div>

        {/* Customize Moods Modal */}
        {showCustomize && (
          <div className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold">Customize Moods</h3>
                <button onClick={() => setShowCustomize(false)} className="px-2 py-1 rounded-md bg-gray-100">✕</button>
              </div>
              <div className="mt-3 space-y-3 max-h-[50vh] overflow-auto pr-2">
                {moods.map((m, idx) => (
                  <div key={idx} className="grid grid-cols-12 gap-2 items-center">
                    <input value={m.emoji} onChange={(e) => updateMoodField(idx, 'emoji', e.target.value)} className="col-span-2 px-2 py-2 border rounded" />
                    <input value={m.label} onChange={(e) => updateMoodField(idx, 'label', e.target.value)} className="col-span-4 px-2 py-2 border rounded" />
                    <input value={m.value} onChange={(e) => updateMoodField(idx, 'value', e.target.value)} className="col-span-4 px-2 py-2 border rounded" />
                    <input value={m.color || ''} onChange={(e) => updateMoodField(idx, 'color', e.target.value)} placeholder="#22c55e" className="col-span-2 px-2 py-2 border rounded" />
                  </div>
                ))}
              </div>
              <div className="mt-4 flex items-center justify-between">
                <button onClick={addMood} className="px-3 py-2 rounded-md bg-gray-800 text-white">Add Mood</button>
                <div className="flex items-center gap-2">
                  <button onClick={() => setShowCustomize(false)} className="px-3 py-2 rounded-md bg-gray-200">Cancel</button>
                  <button onClick={saveMoods} className="px-3 py-2 rounded-md bg-indigo-600 text-white">Save</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;