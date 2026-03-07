import React, { useState, useEffect, useCallback, useRef } from "react";
import "./App.css";
import axios from "axios";
import { useAuth } from "./context/AuthContext";
import LoginPage from "./pages/LoginPage";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";
import { Button } from "./components/ui/button";
import { Input } from "./components/ui/input";
import { Label } from "./components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "./components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./components/ui/dialog";
import { Badge } from "./components/ui/badge";
import { Users, BookOpen, CreditCard, Plus, Edit2, Trash2, UserCheck, Calendar, ChevronDown, ChevronRight, Download, BarChart3, LogOut, Shield, Trophy, CheckCircle, BookMarked, Film, GraduationCap, Star, Stethoscope, Timer, FileText, Eye, Mail, Send, Bell } from "lucide-react";
import { useToast } from "./hooks/use-toast";
import { Toaster } from "./components/ui/toaster";
import { ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Tooltip, XAxis, YAxis, CartesianGrid, AreaChart, Area } from 'recharts';
import * as XLSX from 'xlsx';
import { saveAs } from 'file-saver';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const LIG_ESIKLERI_FE = { bronz: 0, gumus: 200, altin: 500, elmas: 1000 };

function roleLabel(role) {
  const labels = { admin: "Yönetici", coordinator: "Koordinatör", teacher: "Öğretmen", student: "Öğrenci", parent: "Veli" };
  return labels[role] || role;
}

function UserManagement({ teachers }) {
  const { toast } = useToast();
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ ad: "", soyad: "", email: "", telefon: "", password: "", role: "teacher", linked_id: "" });
  const [loading, setLoading] = useState(false);

  const fetchUsers = useCallback(async () => {
    try { const res = await axios.get(`${API}/auth/users`); setUsers(res.data); } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const createUser = async (e) => {
    e.preventDefault(); setLoading(true);
    try {
      await axios.post(`${API}/auth/users`, form);
      setForm({ ad: "", soyad: "", email: "", telefon: "", password: "", role: "teacher", linked_id: "" });
      fetchUsers();
      toast({ title: "Başarılı", description: "Kullanıcı oluşturuldu" });
    } catch (error) {
      toast({ title: "Hata", description: error.response?.data?.detail || "Hata oluştu", variant: "destructive" });
    }
    setLoading(false);
  };

  const deleteUser = async (id) => {
    try { await axios.delete(`${API}/auth/users/${id}`); fetchUsers(); toast({ title: "Başarılı", description: "Kullanıcı silindi" }); }
    catch (error) { toast({ title: "Hata", description: error.response?.data?.detail || "Hata oluştu", variant: "destructive" }); }
  };

  const roleBadgeColor = { admin: "bg-red-100 text-red-700", coordinator: "bg-orange-100 text-orange-700", teacher: "bg-blue-100 text-blue-700", student: "bg-green-100 text-green-700", parent: "bg-purple-100 text-purple-700" };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card className="lg:col-span-1 border-0 shadow-sm">
        <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Kullanıcı</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={createUser} className="space-y-4">
            <div><Label>Ad</Label><Input value={form.ad} onChange={e => setForm({...form, ad: e.target.value})} required /></div>
            <div><Label>Soyad</Label><Input value={form.soyad} onChange={e => setForm({...form, soyad: e.target.value})} required /></div>
            <div><Label>E-posta</Label><Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} required /></div>
            <div><Label>Telefon</Label><Input type="tel" value={form.telefon} onChange={e => setForm({...form, telefon: e.target.value})} placeholder="05xx xxx xx xx" /></div>
            <div><Label>Şifre</Label><Input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} required minLength={6} /></div>
            <div><Label>Rol</Label>
              <Select value={form.role} onValueChange={v => setForm({...form, role: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Yönetici</SelectItem>
                  <SelectItem value="coordinator">Koordinatör</SelectItem>
                  <SelectItem value="teacher">Öğretmen</SelectItem>
                  <SelectItem value="student">Öğrenci</SelectItem>
                  <SelectItem value="parent">Veli</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button type="submit" disabled={loading} className="w-full">Oluştur</Button>
          </form>
        </CardContent>
      </Card>
      <Card className="lg:col-span-2 border-0 shadow-sm">
        <CardHeader><CardTitle>Kullanıcılar</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Ad Soyad</TableHead><TableHead>E-posta</TableHead><TableHead>Telefon</TableHead><TableHead>Rol</TableHead><TableHead>İşlem</TableHead></TableRow></TableHeader>
            <TableBody>
              {users.map(u => (
                <TableRow key={u.id}>
                  <TableCell>{u.ad} {u.soyad}</TableCell>
                  <TableCell>{u.email}</TableCell>
                  <TableCell className="text-gray-500">{u.telefon || '-'}</TableCell>
                  <TableCell><span className={`px-2 py-1 rounded-full text-xs font-medium ${roleBadgeColor[u.role] || 'bg-gray-100'}`}>{roleLabel(u.role)}</span></TableCell>
                  <TableCell><Button variant="destructive" size="sm" onClick={() => deleteUser(u.id)}><Trash2 className="h-4 w-4" /></Button></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function SimpleEditForm({ item, teachers, courses, classes, onSave, onCancel }) {
  const [data, setData] = useState(item.data);
  const handleSubmit = (e) => {
    e.preventDefault();
    const changed = {};
    Object.keys(data).forEach(k => { if (data[k] !== item.data[k]) changed[k] = data[k]; });
    onSave(changed);
  };
  return (
    <form onSubmit={handleSubmit} className="space-y-3 max-h-96 overflow-y-auto">
      <div><Label>Ad</Label><Input value={data.ad||''} onChange={e => setData({...data,ad:e.target.value})} /></div>
      <div><Label>Soyad</Label><Input value={data.soyad||''} onChange={e => setData({...data,soyad:e.target.value})} /></div>
      {item.type === 'teacher' && <>
        <div><Label>Branş</Label><Input value={data.brans||''} onChange={e => setData({...data,brans:e.target.value})} /></div>
        <div><Label>Telefon</Label><Input value={data.telefon||''} onChange={e => setData({...data,telefon:e.target.value})} /></div>
      </>}
      {item.type === 'student' && <>
        <div><Label>Sınıf</Label>
          <Select value={data.sinif} onValueChange={v => setData({...data,sinif:v})}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{classes.map(c=><SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
          </Select>
        </div>
        <div><Label>Veli Adı</Label><Input value={data.veli_ad||''} onChange={e => setData({...data,veli_ad:e.target.value})} /></div>
        <div><Label>Kur</Label><Input value={data.kur||''} onChange={e => setData({...data,kur:e.target.value})} /></div>
        <div><Label>Öğretmen</Label>
          <Select value={data.ogretmen_id||''} onValueChange={v => setData({...data,ogretmen_id:v})}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>{teachers.map(t=><SelectItem key={t.id} value={t.id}>{t.ad} {t.soyad}</SelectItem>)}</SelectContent>
          </Select>
        </div>
      </>}
      {item.type === 'course' && <>
        <div><Label>Fiyat (₺)</Label><Input type="number" value={data.fiyat||0} onChange={e => setData({...data,fiyat:parseFloat(e.target.value)||0})} /></div>
        <div><Label>Süre (Saat)</Label><Input type="number" value={data.sure||0} onChange={e => setData({...data,sure:parseInt(e.target.value)||0})} /></div>
      </>}
      <div className="flex gap-2 pt-2">
        <Button type="submit" className="flex-1">Kaydet</Button>
        <Button type="button" variant="outline" onClick={onCancel} className="flex-1">İptal</Button>
      </div>
    </form>
  );
}

function AppContent() {
  // ── TÜM HOOK'LAR EN ÜSTTE ──
  const { user, logout, loading } = useAuth();
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState("dashboard");
  const [teachers, setTeachers] = useState([]);
  const [students, setStudents] = useState([]);
  const [courses, setCourses] = useState([]);
  const [payments, setPayments] = useState([]);
  const [dashboardStats, setDashboardStats] = useState(null);
  const [bekleyenler, setBekleyenler] = useState(null);
  const [weeklyStats, setWeeklyStats] = useState([]);
  const [monthlyStats, setMonthlyStats] = useState([]);
  const [teacherStudents, setTeacherStudents] = useState({});
  const [expandedTeachers, setExpandedTeachers] = useState(new Set());
  const [loadingAction, setLoadingAction] = useState(false);
  const [teacherForm, setTeacherForm] = useState({ ad: "", soyad: "", brans: "", telefon: "", seviye: "yeni", yapilmasi_gereken_odeme: 0 });
  const [studentForm, setStudentForm] = useState({ ad: "", soyad: "", sinif: "", veli_ad: "", veli_soyad: "", veli_telefon: "", aldigi_egitim: "", kur: "", yapilmasi_gereken_odeme: 0, ogretmene_yapilacak_odeme: 0, ogretmen_id: "" });
  const [courseForm, setCourseForm] = useState({ ad: "", fiyat: 0, sure: 0 });
  const [paymentForm, setPaymentForm] = useState({ tip: "ogrenci", kisi_id: "", miktar: 0, aciklama: "" });
  const [tahsilatDialog, setTahsilatDialog] = useState(null); // {tip: 'ogrenci'|'ogretmen', kisi: {id,ad,soyad}, miktar: 0, aciklama: ''}
  const [editingItem, setEditingItem] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [showArchived, setShowArchived] = useState({ teachers: false, students: false, courses: false });
  const [expandedCourse, setExpandedCourse] = useState(null);
  const [ogrenciRiskler, setOgrenciRiskler] = useState([]);
  const [adminRozetOzet, setAdminRozetOzet] = useState(null);
  const [adminAnketOzet, setAdminAnketOzet] = useState([]);
  const [expandedDers, setExpandedDers] = useState(null);
  const [kursDersleri, setKursDersleri] = useState({});
  const [yeniDersForm, setYeniDersForm] = useState(null);
  const [yeniIcerikForm, setYeniIcerikForm] = useState(null);

  const availableCourses = ["Okuma Becerileri Temel", "Okuma Becerileri İleri", "Hızlı Okuma", "Anlama Becerileri", "Yazım Kuralları", "Dikkat Geliştirme", "Kelime Dağarcığı", "Metin Analizi"];
  const availableClasses = ["1","2","3","4","5","6","7","8","9"];

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${API}/dashboard`); setDashboardStats(r.data); } catch(e) {}
    try { if ((user?.role === 'admin' || user?.role === 'coordinator')) { const r = await axios.get(`${API}/dashboard/bekleyenler`); setBekleyenler(r.data); } } catch(e) { setBekleyenler({ metin_bekleyen:[], metin_oylama:[], gelisim_bekleyen:[], gelisim_oylama:[], kitap_bekleyen:[], kitap_oylama:[], toplam:0 }); }
    try { const r = await axios.get(`${API}/stats/weekly`); setWeeklyStats(Array.isArray(r.data) ? r.data : []); } catch(e) {}
    try { const r = await axios.get(`${API}/stats/monthly`); setMonthlyStats(Array.isArray(r.data) ? r.data : []); } catch(e) {}
    try { const r = await axios.get(`${API}/teachers`); setTeachers(Array.isArray(r.data) ? r.data : []); } catch(e) {}
    try { const r = await axios.get(`${API}/students`); setStudents(Array.isArray(r.data) ? r.data : []); } catch(e) {}
    try { const r = await axios.get(`${API}/courses`); setCourses(Array.isArray(r.data) ? r.data : []); } catch(e) {}
    try { const r = await axios.get(`${API}/payments`); setPayments(Array.isArray(r.data) ? r.data : []); } catch(e) {}
    try { const r = await axios.get(`${API}/risk-skor/toplu`); setOgrenciRiskler(Array.isArray(r.data) ? r.data : []); } catch(e) { setOgrenciRiskler([]); }
  }, []);

  // Admin rozet + anket özeti — ayrı useEffect (fetchAll'dan bağımsız)
  useEffect(() => {
    if (!user || (user.role !== "admin" && user.role !== "coordinator")) return;
    const fetchRozetAnket = async () => {
      try {
        const [rozetR, usersR] = await Promise.all([
          axios.get(`${API}/rozetler/tanim`),
          axios.get(`${API}/auth/users`),
        ]);
        const ogretmenTanim = rozetR.data?.ogretmen || [];
        const allUsers = Array.isArray(usersR.data) ? usersR.data : [];
        const ogretmenUsers = allUsers.filter(u => u.role === "teacher").slice(0, 10);
        const anketOzetleri = [];
        for (const ou of ogretmenUsers) {
          try {
            const [rozR, ankR] = await Promise.all([
              axios.get(`${API}/rozetler/${ou.id}`),
              axios.get(`${API}/anketler/ogretmen/${ou.linked_id || ou.id}/ozet`),
            ]);
            anketOzetleri.push({ id: ou.id, ad: ou.ad, soyad: ou.soyad, rozet_sayisi: Array.isArray(rozR.data) ? rozR.data.length : 0, rozet_toplam: ogretmenTanim.length, anket: ankR.data || {} });
          } catch(e) {}
        }
        setAdminRozetOzet({ ogretmen_tanim: ogretmenTanim.length, ogrenci_tanim: (rozetR.data?.ogrenci || []).length });
        setAdminAnketOzet(anketOzetleri);
      } catch(e) {}
    };
    fetchRozetAnket();
  }, [user]);

  useEffect(() => {
    if (user) fetchAll();
  }, [user, fetchAll]);

  // ── KOŞULLU RETURN'LER HOOK'LARDAN SONRA ──
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-16 h-16 bg-gradient-to-br from-orange-400 to-red-500 rounded-2xl flex items-center justify-center">
          <BookOpen className="h-8 w-8 text-white" />
        </div>
      </div>
    );
  }

  if (!user) return <LoginPage />;

  // Öğrenci rolü → ayrı panel
  if (user.role === "student") return <OgrenciPaneli user={user} logout={logout} />;

  // Veli rolü → ayrı panel
  if (user.role === "parent") return <VeliPaneli user={user} logout={logout} />;

  // Öğretmen rolü → ayrı panel
  if (user.role === "teacher") return <OgretmenPaneli user={user} logout={logout} />;

  const fetchTeachers = async () => { try { const r = await axios.get(`${API}/teachers`); setTeachers(r.data); } catch(e) {} };
  const fetchStudents = async () => { try { const r = await axios.get(`${API}/students`); setStudents(r.data); } catch(e) {} };
  const fetchCourses = async () => { try { const r = await axios.get(`${API}/courses`); setCourses(r.data); } catch(e) {} };
  const fetchKursDersleri = async (kursId) => { try { const r = await axios.get(`${API}/courses/${kursId}/dersler`); setKursDersleri(prev => ({...prev, [kursId]: r.data})); } catch(e) {} };
  const fetchPayments = async () => { try { const r = await axios.get(`${API}/payments`); setPayments(r.data); } catch(e) {} };
  const fetchDashboard = async () => { try { const r = await axios.get(`${API}/dashboard`); setDashboardStats(r.data); } catch(e) {} };
  const fetchTeacherStudents = async (id) => { try { const r = await axios.get(`${API}/teachers/${id}/students`); setTeacherStudents(p => ({...p, [id]: r.data})); } catch(e) {} };

  const toggleTeacherExpansion = (id) => {
    const next = new Set(expandedTeachers);
    if (next.has(id)) { next.delete(id); } else { next.add(id); if (!teacherStudents[id]) fetchTeacherStudents(id); }
    setExpandedTeachers(next);
  };

  const formatCurrency = (v) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(v);
  const toggleCourseExpand = (id) => { if (expandedCourse === id) { setExpandedCourse(null); } else { setExpandedCourse(id); if (!kursDersleri[id]) fetchKursDersleri(id); } };
  const formatDate = (d) => new Date(d).toLocaleDateString('tr-TR');

  const handleEdit = async (updatedData) => {
    try {
      if (editingItem.type === 'teacher') { await axios.put(`${API}/teachers/${editingItem.data.id}`, updatedData); fetchTeachers(); toast({ title: "Başarılı", description: "Güncellendi" }); }
      else if (editingItem.type === 'student') { await axios.put(`${API}/students/${editingItem.data.id}`, updatedData); fetchStudents(); fetchTeachers(); setTeacherStudents({}); toast({ title: "Başarılı", description: "Güncellendi" }); }
      else if (editingItem.type === 'course') { await axios.put(`${API}/courses/${editingItem.data.id}`, updatedData); fetchCourses(); toast({ title: "Başarılı", description: "Güncellendi" }); }
      fetchDashboard(); setEditDialogOpen(false); setEditingItem(null);
    } catch { toast({ title: "Hata", description: "Güncelleme hatası", variant: "destructive" }); }
  };

  const createTeacher = async (e) => { e.preventDefault(); setLoadingAction(true); try { await axios.post(`${API}/teachers`, teacherForm); setTeacherForm({ ad:"",soyad:"",brans:"",telefon:"",seviye:"yeni",yapilmasi_gereken_odeme:0 }); fetchTeachers(); fetchDashboard(); toast({ title:"Başarılı", description:"Öğretmen eklendi" }); } catch { toast({ title:"Hata", description:"Hata oluştu", variant:"destructive" }); } setLoadingAction(false); };
  const createStudent = async (e) => { e.preventDefault(); setLoadingAction(true); try { await axios.post(`${API}/students`, studentForm); setStudentForm({ ad:"",soyad:"",sinif:"",veli_ad:"",veli_soyad:"",veli_telefon:"",aldigi_egitim:"",kur:"",yapilmasi_gereken_odeme:0,ogretmene_yapilacak_odeme:0,ogretmen_id:"" }); fetchStudents(); fetchTeachers(); fetchDashboard(); setTeacherStudents({}); toast({ title:"Başarılı", description:"Öğrenci eklendi" }); } catch { toast({ title:"Hata", description:"Hata oluştu", variant:"destructive" }); } setLoadingAction(false); };
  const createCourse = async (e) => { e.preventDefault(); setLoadingAction(true); try { await axios.post(`${API}/courses`, courseForm); setCourseForm({ ad:"",fiyat:0,sure:0 }); fetchCourses(); fetchDashboard(); toast({ title:"Başarılı", description:"Kurs eklendi" }); } catch { toast({ title:"Hata", description:"Hata oluştu", variant:"destructive" }); } setLoadingAction(false); };
  const createPayment = async (e) => { e.preventDefault(); setLoadingAction(true); try { await axios.post(`${API}/payments`, paymentForm); setPaymentForm({ tip:"ogrenci",kisi_id:"",miktar:0,aciklama:"" }); fetchPayments(); fetchTeachers(); fetchStudents(); fetchDashboard(); toast({ title:"Başarılı", description:"Ödeme kaydedildi" }); } catch { toast({ title:"Hata", description:"Hata oluştu", variant:"destructive" }); } setLoadingAction(false); };
  const deleteTeacher = async (id) => { try { await axios.delete(`${API}/teachers/${id}`); fetchTeachers(); fetchDashboard(); setTeacherStudents(p => { const n={...p}; delete n[id]; return n; }); toast({ title:"Başarılı", description:"Silindi" }); } catch { toast({ title:"Hata", variant:"destructive" }); } };
  const deleteStudent = async (id) => { try { await axios.delete(`${API}/students/${id}`); fetchStudents(); fetchTeachers(); fetchDashboard(); setTeacherStudents({}); toast({ title:"Başarılı", description:"Silindi" }); } catch { toast({ title:"Hata", variant:"destructive" }); } };
  const deleteCourse = async (id) => { try { await axios.delete(`${API}/courses/${id}`); fetchCourses(); fetchDashboard(); toast({ title:"Başarılı", description:"Silindi" }); } catch { toast({ title:"Hata", variant:"destructive" }); } };

  // ── Arşivleme ──
  const toggleArsiv = async (type, id, current) => {
    try {
      const endpoint = type === 'teacher' ? 'teachers' : type === 'student' ? 'students' : 'courses';
      await axios.put(`${API}/${endpoint}/${id}`, { arsivli: !current });
      if (type === 'teacher') fetchTeachers();
      else if (type === 'student') { fetchStudents(); fetchTeachers(); }
      else fetchCourses();
      toast({ title: current ? "Arşivden çıkarıldı" : "Arşivlendi" });
    } catch { toast({ title: "Hata", variant: "destructive" }); }
  };

  // ── Ders Yönetimi ──
  const exportToExcel = async () => {
    setLoadingAction(true);
    try {
      const r = await axios.get(`${API}/export`); const d = r.data;
      const wb = XLSX.utils.book_new();
      if (d.ogretmenler?.length) XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(d.ogretmenler), "Öğretmenler");
      if (d.ogrenciler?.length) XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(d.ogrenciler), "Öğrenciler");
      if (d.kurslar?.length) XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(d.kurslar), "Kurslar");
      if (d.odemeler?.length) XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(d.odemeler), "Ödemeler");
      const buf = XLSX.write(wb, { bookType:'xlsx', type:'array' });
      saveAs(new Blob([buf], { type:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }), `OBA_${new Date().toISOString().slice(0,10)}.xlsx`);
      toast({ title:"Başarılı", description:"Excel indirildi" });
    } catch { toast({ title:"Hata", description:"Export hatası", variant:"destructive" }); }
    setLoadingAction(false);
  };

  const pieData = dashboardStats ? [
    { name:'Öğrenci Alacakları', value:dashboardStats.toplam_ogrenci_alacak, color:'#059669' },
    { name:'Öğretmen Borçları', value:dashboardStats.toplam_ogretmen_borc, color:'#dc2626' }
  ] : [];

  const tabClass = "inline-flex items-center justify-center whitespace-nowrap rounded-xl px-4 py-2 text-sm font-medium transition-all data-[state=active]:bg-gradient-to-r data-[state=active]:from-orange-500 data-[state=active]:to-red-500 data-[state=active]:text-white data-[state=active]:shadow-sm";

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto p-4">
        {/* Header */}
        <div className="bg-white rounded-3xl shadow-sm p-6 mb-6 border border-gray-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="w-14 h-14 bg-gradient-to-br from-orange-400 to-red-500 rounded-2xl flex items-center justify-center">
                <BookOpen className="h-7 w-7 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Okuma Becerileri Akademisi</h1>
                <p className="text-gray-500 text-sm">Eğitim Yönetim Sistemi</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right hidden sm:block">
                <div className="text-sm font-medium text-gray-900">{user.ad} {user.soyad}</div>
                <div className="text-xs text-gray-500">{roleLabel(user.role)}</div>
              </div>
              <BildirimZili user={user} />
              <Button onClick={exportToExcel} disabled={loadingAction} className="bg-green-600 hover:bg-green-700 text-white"><Download className="h-4 w-4 mr-2" />Excel</Button>
              <Button variant="outline" size="sm" onClick={logout} className="flex items-center gap-2"><LogOut className="h-4 w-4" />Çıkış</Button>
            </div>
          </div>
        </div>

        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="inline-flex h-12 items-center justify-center rounded-2xl bg-white p-1 shadow-sm border border-gray-200 flex-wrap gap-1 mb-6">
            <TabsTrigger value="dashboard" className={tabClass}><BarChart3 className="h-4 w-4 mr-2" />Dashboard</TabsTrigger>
            <TabsTrigger value="teachers" className={tabClass}><UserCheck className="h-4 w-4 mr-2" />Öğretmenler</TabsTrigger>
            <TabsTrigger value="students" className={tabClass}><Users className="h-4 w-4 mr-2" />Öğrenciler</TabsTrigger>
            {user.role !== "coordinator" && <TabsTrigger value="payments" className={tabClass}><CreditCard className="h-4 w-4 mr-2" />Muhasebe</TabsTrigger>}
            {user.role === "admin" && <TabsTrigger value="users" className={tabClass}><Shield className="h-4 w-4 mr-2" />Kullanıcılar</TabsTrigger>}
            <TabsTrigger value="gelisim" className={tabClass}><Trophy className="h-4 w-4 mr-2" />Gelişim</TabsTrigger>
            <TabsTrigger value="giris-analizi" className={tabClass}><Stethoscope className="h-4 w-4 mr-2" />Giriş Analizi</TabsTrigger>
            <TabsTrigger value="mesajlar" className={tabClass}><Mail className="h-4 w-4 mr-2" />Mesajlar</TabsTrigger>
            {user.role === "admin" && <TabsTrigger value="ayarlar" className={tabClass}><Star className="h-4 w-4 mr-2" />Ayarlar</TabsTrigger>}
            <TabsTrigger value="ai-merkezi" className={tabClass}>🧠 AI Merkezi</TabsTrigger>
          </TabsList>

          {/* Dashboard */}
          <TabsContent value="dashboard">
            {dashboardStats && (
              <div className="space-y-6">
                {/* KPI: Risk Durumu + Okuma Aktivitesi */}
                {ogrenciRiskler.length > 0 && (
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <div className="bg-gradient-to-br from-green-50 to-emerald-100 rounded-2xl p-4 border border-green-200">
                      <div className="text-xs text-green-600 font-medium">🟢 Düşük Risk</div>
                      <div className="text-3xl font-bold text-green-800">{ogrenciRiskler.filter(r => r.risk_seviye === "dusuk").length}</div>
                      <div className="text-[10px] text-green-500">öğrenci</div>
                    </div>
                    <div className="bg-gradient-to-br from-yellow-50 to-amber-100 rounded-2xl p-4 border border-yellow-200">
                      <div className="text-xs text-yellow-600 font-medium">🟡 Orta Risk</div>
                      <div className="text-3xl font-bold text-yellow-800">{ogrenciRiskler.filter(r => r.risk_seviye === "orta").length}</div>
                      <div className="text-[10px] text-yellow-500">öğrenci</div>
                    </div>
                    <div className="bg-gradient-to-br from-red-50 to-rose-100 rounded-2xl p-4 border border-red-200">
                      <div className="text-xs text-red-600 font-medium">🔴 Yüksek Risk</div>
                      <div className="text-3xl font-bold text-red-800">{ogrenciRiskler.filter(r => r.risk_seviye === "yuksek").length}</div>
                      <div className="text-[10px] text-red-500">öğrenci — müdahale gerekli</div>
                    </div>
                    <div className="bg-gradient-to-br from-blue-50 to-indigo-100 rounded-2xl p-4 border border-blue-200">
                      <div className="text-xs text-blue-600 font-medium">📊 North Star</div>
                      <div className="text-3xl font-bold text-blue-800">{ogrenciRiskler.length > 0 ? Math.round(ogrenciRiskler.filter(r => r.aktif_gunler_7 >= 4).length / ogrenciRiskler.length * 100) : 0}%</div>
                      <div className="text-[10px] text-blue-500">haftada 4+ gün okuyan</div>
                    </div>
                  </div>
                )}

                {/* Riskli öğrenciler uyarısı */}
                {ogrenciRiskler.filter(r => r.risk_seviye === "yuksek").length > 0 && (
                  <Card className="border-0 shadow-sm border-l-4 border-l-red-500">
                    <CardHeader className="pb-2"><CardTitle className="text-sm text-red-700">🚨 Yüksek Riskli Öğrenciler</CardTitle></CardHeader>
                    <CardContent><div className="space-y-2">
                      {ogrenciRiskler.filter(r => r.risk_seviye === "yuksek").slice(0,5).map(r => (
                        <div key={r.id} className="flex items-center justify-between p-2 bg-red-50 rounded-lg">
                          <div><span className="font-medium text-sm">{r.ad} {r.soyad}</span><span className="text-xs text-gray-500 ml-2">{r.sinif}. sınıf</span></div>
                          <div className="flex items-center gap-3 text-xs">
                            <span className="text-gray-500">Streak: {r.streak}</span>
                            <span className="text-gray-500">7g: {r.dakika_7}dk</span>
                            <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-bold">Risk: {r.risk_skoru}</span>
                          </div>
                        </div>
                      ))}
                    </div></CardContent>
                  </Card>
                )}

                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <Card className="border-0 shadow-sm bg-gradient-to-br from-blue-50 to-blue-100 cursor-pointer" onClick={() => setActiveTab("teachers")}>
                    <CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-blue-600">Öğretmen</p><p className="text-3xl font-bold text-blue-900">{dashboardStats.toplam_ogretmen}</p></div><div className="w-12 h-12 bg-blue-500 rounded-2xl flex items-center justify-center"><UserCheck className="h-6 w-6 text-white" /></div></div></CardContent>
                  </Card>
                  <Card className="border-0 shadow-sm bg-gradient-to-br from-green-50 to-green-100 cursor-pointer" onClick={() => setActiveTab("students")}>
                    <CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-green-600">Öğrenci</p><p className="text-3xl font-bold text-green-900">{dashboardStats.toplam_ogrenci}</p></div><div className="w-12 h-12 bg-green-500 rounded-2xl flex items-center justify-center"><Users className="h-6 w-6 text-white" /></div></div></CardContent>
                  </Card>
                  <Card className="border-0 shadow-sm bg-gradient-to-br from-orange-50 to-orange-100 cursor-pointer" onClick={() => setActiveTab("courses")}>
                    <CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-orange-600">Kurs</p><p className="text-3xl font-bold text-orange-900">{dashboardStats.toplam_kurs}</p></div><div className="w-12 h-12 bg-orange-500 rounded-2xl flex items-center justify-center"><BookOpen className="h-6 w-6 text-white" /></div></div></CardContent>
                  </Card>
                  <Card className="border-0 shadow-sm bg-gradient-to-br from-purple-50 to-purple-100 cursor-pointer" onClick={() => setActiveTab("payments")}>
                    <CardContent className="p-6"><div className="flex items-center justify-between"><div><p className="text-sm text-purple-600">Bu Ay</p><p className="text-xl font-bold text-purple-900">{formatCurrency(dashboardStats.bu_ay_odenen_toplam)}</p></div><div className="w-12 h-12 bg-purple-500 rounded-2xl flex items-center justify-center"><Calendar className="h-6 w-6 text-white" /></div></div></CardContent>
                  </Card>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card className="border-0 shadow-sm">
                    <CardHeader><CardTitle>Finansal Durum</CardTitle></CardHeader>
                    <CardContent><div className="h-64"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={100} dataKey="value">{pieData.map((e,i) => <Cell key={i} fill={e.color} />)}</Pie><Tooltip formatter={v => formatCurrency(v)} /></PieChart></ResponsiveContainer></div></CardContent>
                  </Card>
                  <Card className="border-0 shadow-sm">
                    <CardHeader><CardTitle>Aylık İstatistikler</CardTitle></CardHeader>
                    <CardContent><div className="h-64"><ResponsiveContainer width="100%" height="100%"><BarChart data={monthlyStats}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="ay" /><YAxis /><Tooltip /><Bar dataKey="yeni_ogrenciler" fill="#3b82f6" /><Bar dataKey="gelir" fill="#f97316" /></BarChart></ResponsiveContainer></div></CardContent>
                  </Card>
                </div>

                {/* Öğretmen Rozet + Veli Anket Özeti */}
                {adminAnketOzet.length > 0 && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    <Card className="border-0 shadow-sm">
                      <CardHeader><CardTitle className="text-base">🏅 Öğretmen Rozet Durumu</CardTitle></CardHeader>
                      <CardContent><div className="space-y-3">
                        {adminAnketOzet.map(o => (
                          <div key={o.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                            <div><div className="font-medium text-sm">{o.ad} {o.soyad}</div></div>
                            <div className="flex items-center gap-2">
                              <div className="bg-orange-100 rounded-full h-2 w-24 overflow-hidden"><div className="h-2 bg-orange-500 rounded-full" style={{width: `${(o.rozet_sayisi / Math.max(o.rozet_toplam, 1)) * 100}%`}} /></div>
                              <span className="text-xs font-medium text-orange-600">{o.rozet_sayisi}/{o.rozet_toplam}</span>
                            </div>
                          </div>
                        ))}
                      </div></CardContent>
                    </Card>
                    <Card className="border-0 shadow-sm">
                      <CardHeader><CardTitle className="text-base">💜 Veli Değerlendirme Özeti</CardTitle></CardHeader>
                      <CardContent><div className="space-y-3">
                        {adminAnketOzet.map(o => (
                          <div key={o.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
                            <div><div className="font-medium text-sm">{o.ad} {o.soyad}</div><div className="text-xs text-gray-400">{o.anket?.anket_sayisi || 0} anket</div></div>
                            <div className="flex items-center gap-3">
                              {o.anket?.anket_sayisi > 0 ? (<>
                                <span className="text-lg font-bold text-purple-600">⭐{o.anket.ortalama}</span>
                                <span className="text-xs text-green-600 font-medium">%{o.anket.tavsiye_oran} tavsiye</span>
                              </>) : (<span className="text-xs text-gray-400">Anket yok</span>)}
                            </div>
                          </div>
                        ))}
                      </div></CardContent>
                    </Card>
                  </div>
                )}

              </div>
            )}
          </TabsContent>

          {/* Teachers */}
          <TabsContent value="teachers">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card className="lg:col-span-1 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Öğretmen</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={createTeacher} className="space-y-4">
                    <div><Label>Ad</Label><Input value={teacherForm.ad} onChange={e => setTeacherForm({...teacherForm, ad:e.target.value})} required /></div>
                    <div><Label>Soyad</Label><Input value={teacherForm.soyad} onChange={e => setTeacherForm({...teacherForm, soyad:e.target.value})} required /></div>
                    <div><Label>Branş</Label><Input value={teacherForm.brans} onChange={e => setTeacherForm({...teacherForm, brans:e.target.value})} required /></div>
                    <div><Label>Telefon</Label><Input value={teacherForm.telefon} onChange={e => setTeacherForm({...teacherForm, telefon:e.target.value})} required /></div>
                    <div><Label>Seviye</Label>
                      <Select value={teacherForm.seviye} onValueChange={v => setTeacherForm({...teacherForm, seviye:v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="yeni">Yeni</SelectItem><SelectItem value="uzman">Uzman</SelectItem></SelectContent>
                      </Select>
                    </div>
                    <div><Label>Ödeme (₺)</Label><Input type="number" step="0.01" value={teacherForm.yapilmasi_gereken_odeme} onChange={e => setTeacherForm({...teacherForm, yapilmasi_gereken_odeme:parseFloat(e.target.value)||0})} /></div>
                    <Button type="submit" disabled={loadingAction} className="w-full">Ekle</Button>
                  </form>
                </CardContent>
              </Card>
              <Card className="lg:col-span-2 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center justify-between">Öğretmenler <label className="flex items-center gap-2 text-sm font-normal cursor-pointer"><input type="checkbox" checked={showArchived.teachers} onChange={e => setShowArchived(p => ({...p, teachers: e.target.checked}))} className="rounded" /> Arşivi göster</label></CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {teachers.filter(t => showArchived.teachers || !t.arsivli).map(t => (
                      <div key={t.id} className={`border border-gray-100 rounded-2xl overflow-hidden ${t.arsivli ? 'opacity-50 bg-gray-50' : ''}`}>
                        <div className="p-4 cursor-pointer hover:bg-gray-50 flex items-center justify-between" onClick={() => toggleTeacherExpansion(t.id)}>
                          <div className="flex items-center gap-4">
                            {expandedTeachers.has(t.id) ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                            <div><div className="font-medium">{t.ad} {t.soyad}</div><div className="text-sm text-gray-500">{t.brans} • {t.seviye}</div></div>
                          </div>
                          <div className="flex items-center gap-4">
                            <div className="text-center"><div className="text-sm font-medium">{t.ogrenci_sayisi}</div><div className="text-xs text-gray-500">Öğrenci</div></div>
                            <div className="flex gap-2">
                              {user.role !== "coordinator" && <Button variant="outline" size="sm" className="text-green-600 border-green-300 hover:bg-green-50" onClick={e => { e.stopPropagation(); setTahsilatDialog({tip:'ogretmen', kisi:t, miktar:0, aciklama:''}); }}><CreditCard className="h-4 w-4" /></Button>}
                              <Button variant="outline" size="sm" onClick={e => { e.stopPropagation(); setEditingItem({type:'teacher',data:t}); setEditDialogOpen(true); }}><Edit2 className="h-4 w-4" /></Button>
                              <Button variant="outline" size="sm" className={t.arsivli ? "text-green-600 border-green-300" : "text-yellow-600 border-yellow-300"} onClick={e => { e.stopPropagation(); toggleArsiv('teacher', t.id, t.arsivli); }} title={t.arsivli ? "Arşivden Çıkar" : "Arşivle"}>{t.arsivli ? "📂" : "📦"}</Button>
                              <Button variant="destructive" size="sm" onClick={e => { e.stopPropagation(); deleteTeacher(t.id); }}><Trash2 className="h-4 w-4" /></Button>
                            </div>
                          </div>
                        </div>
                        {expandedTeachers.has(t.id) && (() => {
                          const ogretmenOdemeleri = payments.filter(p => p.tip === 'ogretmen' && p.kisi_id === t.id);
                          const toplamOdenen = ogretmenOdemeleri.reduce((sum, p) => sum + (p.miktar || 0), 0);
                          const kalanAlacak = Math.max(0, (t.yapilmasi_gereken_odeme || 0) - toplamOdenen);
                          return (
                          <div className="border-t border-gray-100 bg-gray-50 p-4 space-y-4">
                            {/* Ödeme Özeti - koordinatörden gizle */}
                            {user.role !== "coordinator" && (
                            <div className="grid grid-cols-3 gap-3">
                              <div className="bg-white rounded-xl p-3 border border-gray-200 text-center">
                                <div className="text-xs text-gray-500 mb-1">Yapılacak Ödeme</div>
                                <div className="font-bold text-orange-600">₺{(t.yapilmasi_gereken_odeme || 0).toLocaleString('tr-TR')}</div>
                              </div>
                              <div className="bg-white rounded-xl p-3 border border-gray-200 text-center">
                                <div className="text-xs text-gray-500 mb-1">Toplam Ödenen</div>
                                <div className="font-bold text-green-600">₺{toplamOdenen.toLocaleString('tr-TR')}</div>
                              </div>
                              <div className="bg-white rounded-xl p-3 border border-gray-200 text-center">
                                <div className="text-xs text-gray-500 mb-1">Kalan Alacak</div>
                                <div className={`font-bold ${kalanAlacak > 0 ? 'text-red-600' : 'text-green-600'}`}>₺{kalanAlacak.toLocaleString('tr-TR')}</div>
                              </div>
                            </div>
                            )}
                            {/* Ödeme Geçmişi */}
                            {ogretmenOdemeleri.length > 0 && (
                              <div>
                                <div className="text-xs font-semibold text-gray-500 mb-2">📤 Ödeme Geçmişi</div>
                                {ogretmenOdemeleri.slice(0,5).map(p => (
                                  <div key={p.id} className="flex justify-between items-center bg-white p-2 rounded-lg border border-gray-100 mb-1 text-sm">
                                    <span className="text-gray-500">{formatDate(p.tarih)}</span>
                                    <span className="text-gray-700">{p.aciklama || '—'}</span>
                                    <span className="font-semibold text-green-600">₺{(p.miktar||0).toLocaleString('tr-TR')}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                            {/* Öğrenci Listesi */}
                            {teacherStudents[t.id] && teacherStudents[t.id].length > 0 && (
                              <div>
                                <div className="text-xs font-semibold text-gray-500 mb-2">👨‍🎓 Öğrenciler</div>
                                {teacherStudents[t.id].map(s => (
                                  <div key={s.id} className="bg-white p-2 rounded-lg border border-gray-100 mb-1 flex justify-between text-sm">
                                    <span className="font-medium">{s.ad} {s.soyad}</span>
                                    <span className="text-gray-500">Kur: {s.kur} • {s.sinif}</span>
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                          );
                        })()}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Students */}
          <TabsContent value="students">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card className="lg:col-span-1 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Öğrenci</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={createStudent} className="space-y-4">
                    <div><Label>Ad</Label><Input value={studentForm.ad} onChange={e => setStudentForm({...studentForm, ad:e.target.value})} required /></div>
                    <div><Label>Soyad</Label><Input value={studentForm.soyad} onChange={e => setStudentForm({...studentForm, soyad:e.target.value})} required /></div>
                    <div><Label>Sınıf</Label>
                      <Select value={studentForm.sinif} onValueChange={v => setStudentForm({...studentForm, sinif:v})}>
                        <SelectTrigger><SelectValue placeholder="Seçin" /></SelectTrigger>
                        <SelectContent>{availableClasses.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div><Label>Veli Adı</Label><Input value={studentForm.veli_ad} onChange={e => setStudentForm({...studentForm, veli_ad:e.target.value})} required /></div>
                    <div><Label>Veli Soyadı</Label><Input value={studentForm.veli_soyad} onChange={e => setStudentForm({...studentForm, veli_soyad:e.target.value})} required /></div>
                    <div><Label>Veli Telefon</Label><Input value={studentForm.veli_telefon} onChange={e => setStudentForm({...studentForm, veli_telefon:e.target.value})} required /></div>
                    <div><Label>Eğitim</Label>
                      <Select value={studentForm.aldigi_egitim} onValueChange={v => setStudentForm({...studentForm, aldigi_egitim:v})}>
                        <SelectTrigger><SelectValue placeholder="Seçin" /></SelectTrigger>
                        <SelectContent>{availableCourses.map(c => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div><Label>Kur</Label><Input value={studentForm.kur} onChange={e => setStudentForm({...studentForm, kur:e.target.value})} required /></div>
                    <div><Label>Ödeme (₺)</Label><Input type="number" step="0.01" value={studentForm.yapilmasi_gereken_odeme} onChange={e => setStudentForm({...studentForm, yapilmasi_gereken_odeme:parseFloat(e.target.value)||0})} /></div>
                    <div><Label>Öğretmen Payı (₺)</Label><Input type="number" step="0.01" value={studentForm.ogretmene_yapilacak_odeme} onChange={e => setStudentForm({...studentForm, ogretmene_yapilacak_odeme:parseFloat(e.target.value)||0})} /></div>
                    <div><Label>Öğretmen</Label>
                      <Select value={studentForm.ogretmen_id} onValueChange={v => setStudentForm({...studentForm, ogretmen_id:v})}>
                        <SelectTrigger><SelectValue placeholder="Seçin" /></SelectTrigger>
                        <SelectContent>{teachers.map(t => <SelectItem key={t.id} value={t.id}>{t.ad} {t.soyad}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <Button type="submit" disabled={loadingAction} className="w-full">Ekle</Button>
                  </form>
                </CardContent>
              </Card>
              <Card className="lg:col-span-2 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center justify-between">Öğrenciler <label className="flex items-center gap-2 text-sm font-normal cursor-pointer"><input type="checkbox" checked={showArchived.students} onChange={e => setShowArchived(p => ({...p, students: e.target.checked}))} className="rounded" /> Arşivi göster</label></CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader><TableRow><TableHead>Ad Soyad</TableHead><TableHead>Sınıf</TableHead><TableHead>Kur</TableHead><TableHead>Risk</TableHead><TableHead>Streak</TableHead><TableHead>XP</TableHead><TableHead>Öğretmen</TableHead>{user.role !== "coordinator" && <TableHead>Borç</TableHead>}<TableHead>İşlem</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {students.filter(s => showArchived.students || !s.arsivli).map(s => {
                        const t = teachers.find(t => t.id === s.ogretmen_id);
                        const risk = ogrenciRiskler.find(r => r.id === s.id);
                        const riskRenk = risk ? (risk.risk_seviye === "yuksek" ? "bg-red-100 text-red-700" : risk.risk_seviye === "orta" ? "bg-yellow-100 text-yellow-700" : "bg-green-100 text-green-700") : "bg-gray-100 text-gray-500";
                        const riskIcon = risk ? (risk.risk_seviye === "yuksek" ? "🔴" : risk.risk_seviye === "orta" ? "🟡" : "🟢") : "⚪";
                        return (
                          <TableRow key={s.id} className={s.arsivli ? 'opacity-50 bg-gray-50' : ''}>
                            <TableCell className="font-medium">{s.ad} {s.soyad}</TableCell>
                            <TableCell>{s.sinif}</TableCell>
                            <TableCell><span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded-full">{s.kur || "—"}</span></TableCell>
                            <TableCell><span className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${riskRenk}`}>{riskIcon} {risk?.risk_skoru || 0}</span></TableCell>
                            <TableCell>{risk ? <span className="text-sm">{risk.streak > 0 ? `🔥${risk.streak}` : "—"}</span> : "—"}</TableCell>
                            <TableCell><span className="text-xs font-medium text-orange-600">{risk?.toplam_xp || s.toplam_xp || 0}</span></TableCell>
                            <TableCell>{t ? `${t.ad} ${t.soyad}` : '-'}</TableCell>
                            {user.role !== "coordinator" && <TableCell className="text-green-600 font-semibold">{formatCurrency(Math.max(0, s.yapilmasi_gereken_odeme - s.yapilan_odeme))}</TableCell>}
                            <TableCell><div className="flex gap-2">{user.role !== "coordinator" && <Button variant="outline" size="sm" className="text-green-600 border-green-300 hover:bg-green-50" onClick={() => setTahsilatDialog({tip:'ogrenci', kisi:s, miktar:0, aciklama:''})}><CreditCard className="h-4 w-4" /></Button>}<Button variant="outline" size="sm" onClick={() => { setEditingItem({type:'student',data:s}); setEditDialogOpen(true); }}><Edit2 className="h-4 w-4" /></Button><Button variant="outline" size="sm" className={s.arsivli ? "text-green-600 border-green-300" : "text-yellow-600 border-yellow-300"} onClick={() => toggleArsiv('student', s.id, s.arsivli)} title={s.arsivli ? "Arşivden Çıkar" : "Arşivle"}>{s.arsivli ? "📂" : "📦"}</Button><Button variant="destructive" size="sm" onClick={() => deleteStudent(s.id)}><Trash2 className="h-4 w-4" /></Button></div></TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Courses */}
          <TabsContent value="courses">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card className="lg:col-span-1 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Kurs</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={createCourse} className="space-y-4">
                    <div><Label>Kurs Adı</Label><Input value={courseForm.ad} onChange={e => setCourseForm({...courseForm, ad:e.target.value})} required /></div>
                    <div><Label>Fiyat (₺)</Label><Input type="number" step="0.01" value={courseForm.fiyat} onChange={e => setCourseForm({...courseForm, fiyat:parseFloat(e.target.value)||0})} required /></div>
                    <div><Label>Süre (Saat)</Label><Input type="number" value={courseForm.sure} onChange={e => setCourseForm({...courseForm, sure:parseInt(e.target.value)||0})} required /></div>
                    <Button type="submit" disabled={loadingAction} className="w-full">Ekle</Button>
                  </form>
                </CardContent>
              </Card>
              <Card className="lg:col-span-2 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center justify-between">Kurslar <label className="flex items-center gap-2 text-sm font-normal cursor-pointer"><input type="checkbox" checked={showArchived.courses} onChange={e => setShowArchived(p => ({...p, courses: e.target.checked}))} className="rounded" /> Arşivi göster</label></CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  {courses.filter(c => showArchived.courses || !c.arsivli).map(c => {
                    const isExpanded = expandedCourse === c.id;
                    return (
                      <div key={c.id} className={`border border-gray-200 rounded-xl overflow-hidden ${c.arsivli ? 'opacity-50 bg-gray-50' : ''}`}>
                        <div className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50" onClick={() => toggleCourseExpand(c.id)}>
                          <div className="flex items-center gap-3">
                            <span className="text-lg">{isExpanded ? '▼' : '▶'}</span>
                            <div>
                              <div className="font-semibold">{c.ad}</div>
                              <div className="text-sm text-gray-500">{formatCurrency(c.fiyat)} • {c.sure} saat • {(kursDersleri[c.id] || []).length} ders</div>
                            </div>
                          </div>
                          <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                            <Button variant="outline" size="sm" onClick={() => { setEditingItem({type:'course',data:c}); setEditDialogOpen(true); }}><Edit2 className="h-4 w-4" /></Button>
                            <Button variant="outline" size="sm" className={c.arsivli ? "text-green-600 border-green-300" : "text-yellow-600 border-yellow-300"} onClick={() => toggleArsiv('course', c.id, c.arsivli)} title={c.arsivli ? "Arşivden Çıkar" : "Arşivle"}>{c.arsivli ? "📂" : "📦"}</Button>
                            <Button variant="destructive" size="sm" onClick={() => deleteCourse(c.id)}><Trash2 className="h-4 w-4" /></Button>
                          </div>
                        </div>
                        {isExpanded && (
                          <div className="border-t border-gray-100 bg-gray-50 p-4 space-y-4">
                            <div className="flex items-center justify-between">
                              <h4 className="font-semibold text-sm">📚 Dersler</h4>
                              <Button size="sm" className="bg-blue-600 hover:bg-blue-700 text-white" onClick={() => setYeniDersForm({kurs_id: c.id, baslik: '', ozet: '', _acik: true})}>+ Ders Ekle</Button>
                            </div>
                            {yeniDersForm?._acik && yeniDersForm?.kurs_id === c.id && (
                              <div className="bg-white p-3 rounded-lg border border-blue-200 space-y-2">
                                <Input placeholder="Ders başlığı" value={yeniDersForm.baslik} onChange={e => setYeniDersForm({...yeniDersForm, baslik: e.target.value})} />
                                <textarea className="w-full border rounded-lg p-2 text-sm" rows={2} placeholder="Ders özeti..." value={yeniDersForm.ozet} onChange={e => setYeniDersForm({...yeniDersForm, ozet: e.target.value})} />
                                <div className="flex gap-2">
                                  <Button size="sm" className="bg-blue-600 text-white" onClick={async () => {
                                    if (!yeniDersForm.baslik) return;
                                    try {
                                      const sira = (kursDersleri[c.id] || []).length + 1;
                                      await axios.post(`${API}/courses/${c.id}/dersler`, { baslik: yeniDersForm.baslik, ozet: yeniDersForm.ozet, sira });
                                      setYeniDersForm(null);
                                      fetchKursDersleri(c.id);
                                      toast({title: "Ders eklendi"});
                                    } catch { toast({title:"Hata", variant:"destructive"}); }
                                  }}>Kaydet</Button>
                                  <Button size="sm" variant="outline" onClick={() => setYeniDersForm(null)}>İptal</Button>
                                </div>
                              </div>
                            )}
                            {(kursDersleri[c.id] || []).length === 0 && <p className="text-sm text-gray-400 italic">Henüz ders eklenmemiş</p>}
                            {(kursDersleri[c.id] || []).map((ders, di) => (
                              <div key={ders.id} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
                                <div className="flex items-center justify-between p-3 cursor-pointer hover:bg-blue-50" onClick={() => setExpandedDers(expandedDers === ders.id ? null : ders.id)}>
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs font-bold text-blue-600 bg-blue-100 rounded-full w-6 h-6 flex items-center justify-center">{di+1}</span>
                                    <div>
                                      <div className="font-medium text-sm">{ders.baslik}</div>
                                      {ders.ozet && <div className="text-xs text-gray-500">{ders.ozet.slice(0,80)}{ders.ozet.length > 80 ? '...' : ''}</div>}
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                                    <span className="text-xs text-gray-400">{(ders.icerikler || []).length} içerik</span>
                                    <Button variant="outline" size="sm" className="h-7 w-7 p-0" onClick={async () => {
                                      if (confirm('Bu dersi silmek istediğinize emin misiniz?')) {
                                        await axios.delete(`${API}/dersler/${ders.id}`);
                                        fetchKursDersleri(c.id);
                                        toast({title: "Ders silindi"});
                                      }
                                    }}><Trash2 className="h-3 w-3" /></Button>
                                  </div>
                                </div>
                                {expandedDers === ders.id && (
                                  <div className="border-t border-gray-100 p-3 space-y-3 bg-blue-50/30">
                                    <div className="flex items-center justify-between">
                                      <span className="text-xs font-semibold text-gray-600">📎 İçerikler</span>
                                      <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => setYeniIcerikForm({ders_id: ders.id, kurs_id: c.id, tur: 'video', baslik: '', url: '', ozet: '', _acik: true, _egzersizId: ''})}>+ İçerik Ekle</Button>
                                    </div>
                                    {yeniIcerikForm?._acik && yeniIcerikForm?.ders_id === ders.id && (
                                      <div className="bg-white p-3 rounded-lg border border-green-200 space-y-2">
                                        <div className="flex gap-2 flex-wrap">
                                          {['video','pdf','docx','embed','egzersiz'].map(t => (
                                            <button key={t} className={`px-3 py-1 rounded-full text-xs font-medium border ${yeniIcerikForm.tur === t ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-300'}`} onClick={() => setYeniIcerikForm({...yeniIcerikForm, tur: t, _egzersizId: '', baslik: t === 'egzersiz' ? '' : yeniIcerikForm.baslik, url: t === 'egzersiz' ? '' : yeniIcerikForm.url})}>
                                              {t === 'video' ? '🎬 Video' : t === 'pdf' ? '📄 PDF' : t === 'docx' ? '📝 Doküman' : t === 'embed' ? '🌐 Web Embed' : '🎯 Egzersiz'}
                                            </button>
                                          ))}
                                        </div>
                                        {yeniIcerikForm.tur === 'egzersiz' ? (
                                          <div className="space-y-2">
                                            <p className="text-xs text-gray-500 font-medium">Bir egzersiz seçin:</p>
                                            <div className="grid grid-cols-2 gap-2">
                                              {[
                                                {id:'goz-takip', icon:'👁️', ad:'Göz Takip', aciklama:'Hareket eden topu takip edin'},
                                                {id:'goz-sekiz', icon:'♾️', ad:'Sonsuzluk (∞)', aciklama:'Sonsuzluk şeklinde göz hareketi'},
                                                {id:'goz-zigzag', icon:'⚡', ad:'Zigzag Okuma', aciklama:'Satır takip hızını artırır'},
                                                {id:'goz-genisletme', icon:'🔭', ad:'Görüş Alanı Genişletme', aciklama:'Çevresel görüşü genişletin'},
                                                {id:'hizli-kelime', icon:'📖', ad:'Hızlı Kelime (RSVP)', aciklama:'Kelimeler tek tek gösterilir'},
                                                {id:'odaklanma', icon:'🎯', ad:'Odaklanma Noktası', aciklama:'Merkeze odaklan, çevreyi oku'},
                                                {id:'periferik', icon:'👀', ad:'Periferik Görüş', aciklama:'Çevresel görüş egzersizi'},
                                                {id:'schulte', icon:'🔢', ad:'Schulte Tablosu', aciklama:'Sayıları sırayla bul'},
                                                {id:'goz-yoga', icon:'🧘', ad:'Göz Yoga', aciklama:'Uzak-yakın odaklanma'},
                                                {id:'renk-eslestir', icon:'🎨', ad:'Renk Eşleştirme', aciklama:'Hızlı renk algılama'},
                                                {id:'kelime-avcisi', icon:'🔍', ad:'Kelime Avcısı', aciklama:'Metinde hedef kelime bul'},
                                                {id:'ters-kelime', icon:'🔄', ad:'Ters Kelime Okuma', aciklama:'Beyin jimnastiği'},
                                                {id:'eksik-harf', icon:'✏️', ad:'Eksik Harf Tamamlama', aciklama:'Eksik harfleri tamamla'},
                                                {id:'karisik-cumle', icon:'🧩', ad:'Karışık Cümle Düzenleme', aciklama:'Cümleyi doğru sırala'},
                                              ].map(eg => (
                                                <div key={eg.id} className={`p-2 rounded-lg border cursor-pointer transition-all ${yeniIcerikForm._egzersizId === eg.id ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-200' : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50/50'}`}
                                                  onClick={() => setYeniIcerikForm({...yeniIcerikForm, _egzersizId: eg.id, baslik: eg.ad, url: `egzersiz://${eg.id}`, ozet: eg.aciklama})}>
                                                  <div className="flex items-center gap-2">
                                                    <span className="text-xl">{eg.icon}</span>
                                                    <div>
                                                      <div className="text-xs font-semibold">{eg.ad}</div>
                                                      <div className="text-xs text-gray-400">{eg.aciklama}</div>
                                                    </div>
                                                  </div>
                                                </div>
                                              ))}
                                            </div>
                                          </div>
                                        ) : (
                                          <>
                                            <Input placeholder="İçerik başlığı" value={yeniIcerikForm.baslik} onChange={e => setYeniIcerikForm({...yeniIcerikForm, baslik: e.target.value})} />
                                            <Input placeholder="URL (video linki, dosya linki...)" value={yeniIcerikForm.url} onChange={e => setYeniIcerikForm({...yeniIcerikForm, url: e.target.value})} />
                                          </>
                                        )}
                                        <textarea className="w-full border rounded-lg p-2 text-sm" rows={2} placeholder="İçerik özeti..." value={yeniIcerikForm.ozet} onChange={e => setYeniIcerikForm({...yeniIcerikForm, ozet: e.target.value})} />
                                        <div className="flex gap-2">
                                          <Button size="sm" className="bg-green-600 text-white" onClick={async () => {
                                            if (!yeniIcerikForm.baslik) return;
                                            try {
                                              await axios.post(`${API}/dersler/${ders.id}/icerik`, { tur: yeniIcerikForm.tur, baslik: yeniIcerikForm.baslik, url: yeniIcerikForm.url, ozet: yeniIcerikForm.ozet });
                                              setYeniIcerikForm(null);
                                              fetchKursDersleri(c.id);
                                              toast({title: "İçerik eklendi"});
                                            } catch { toast({title:"Hata", variant:"destructive"}); }
                                          }}>Kaydet</Button>
                                          <Button size="sm" variant="outline" onClick={() => setYeniIcerikForm(null)}>İptal</Button>
                                        </div>
                                      </div>
                                    )}
                                    {(ders.icerikler || []).length === 0 && !yeniIcerikForm?._acik && <p className="text-xs text-gray-400 italic">Henüz içerik eklenmemiş</p>}
                                    {(ders.icerikler || []).map(ic => {
                                      const isYoutube = ic.url && (ic.url.includes('youtube.com') || ic.url.includes('youtu.be'));
                                      const ytId = isYoutube ? (ic.url.match(/(?:v=|youtu\.be\/)([\w-]+)/)?.[1] || '') : '';
                                      const isEgzersiz = ic.url && ic.url.startsWith('egzersiz://');
                                      const egzersizId = isEgzersiz ? ic.url.replace('egzersiz://', '') : '';
                                      const isEmbed = (ic.tur === 'embed') || (ic.tur === 'egzersiz' && !isEgzersiz);
                                      const isPdf = ic.url && ic.url.endsWith('.pdf');
                                      const showEmbed = ic._embed || false;
                                      return (
                                      <div key={ic.id} className="bg-white rounded-lg border border-gray-100 overflow-hidden">
                                        <div className="flex items-center justify-between p-2">
                                          <div className="flex items-center gap-2 flex-1">
                                            <span className="text-lg">{isEgzersiz ? '🎯' : ic.tur === 'video' ? '🎬' : ic.tur === 'pdf' ? '📄' : ic.tur === 'embed' ? '🌐' : '📝'}</span>
                                            <div className="flex-1">
                                              <div className="text-sm font-medium">{ic.baslik}</div>
                                              {ic.ozet && <div className="text-xs text-gray-500">{ic.ozet.slice(0,80)}{ic.ozet.length > 80 ? '...' : ''}</div>}
                                            </div>
                                          </div>
                                          <div className="flex items-center gap-1">
                                            {isEgzersiz && (
                                              <Button size="sm" className="h-7 text-xs bg-gradient-to-r from-blue-500 to-cyan-500 text-white" onClick={() => { setActiveTab('egzersizler'); }}>▶ Egzersizi Başlat</Button>
                                            )}
                                            {ic.url && !isEgzersiz && (isYoutube || isEmbed || isPdf) && (
                                              <Button variant="outline" size="sm" className="h-7 text-xs text-blue-600 border-blue-300" onClick={() => {
                                                const updated = (kursDersleri[c.id] || []).map(d => d.id === ders.id ? {...d, icerikler: d.icerikler.map(i => i.id === ic.id ? {...i, _embed: !i._embed} : i)} : d);
                                                setKursDersleri(prev => ({...prev, [c.id]: updated}));
                                              }}>{showEmbed ? '▲ Kapat' : '▶ Aç'}</Button>
                                            )}
                                            {ic.url && !isYoutube && !isEmbed && !isPdf && !isEgzersiz && <a href={ic.url} target="_blank" rel="noreferrer" className="text-xs text-blue-500 hover:underline mr-2">🔗 Aç</a>}
                                            <Button variant="outline" size="sm" className="h-7 w-7 p-0 text-red-500" onClick={async () => {
                                              await axios.delete(`${API}/dersler/${ders.id}/icerik/${ic.id}`);
                                              fetchKursDersleri(c.id);
                                              toast({title: "İçerik silindi"});
                                            }}><Trash2 className="h-3 w-3" /></Button>
                                          </div>
                                        </div>
                                        {showEmbed && ic.url && (
                                          <div className="border-t border-gray-100 p-2 bg-gray-50">
                                            {isYoutube && ytId ? (
                                              <div className="relative w-full" style={{paddingBottom:'56.25%'}}><iframe src={`https://www.youtube.com/embed/${ytId}`} className="absolute inset-0 w-full h-full rounded-lg" allowFullScreen allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" /></div>
                                            ) : isPdf ? (
                                              <iframe src={ic.url} className="w-full rounded-lg border" style={{height:'500px'}} />
                                            ) : (
                                              <iframe src={ic.url} className="w-full rounded-lg border" style={{height:'500px'}} sandbox="allow-scripts allow-same-origin allow-popups" />
                                            )}
                                          </div>
                                        )}
                                      </div>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Payments */}
          <TabsContent value="payments">
            {/* Özet Kartları */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <Card className="border-0 shadow-sm bg-gradient-to-br from-green-50 to-emerald-100">
                <CardContent className="p-5 text-center">
                  <div className="text-sm text-green-700 font-medium mb-2">📥 Öğrenci Ödemeleri</div>
                  <div className="text-xs text-gray-500 mb-1">Alınması Gereken</div>
                  <div className="text-2xl font-bold text-green-800">{formatCurrency(students.reduce((s, st) => s + (st.yapilmasi_gereken_odeme || 0), 0))}</div>
                  <div className="border-t border-green-200 my-2"></div>
                  <div className="text-xs text-gray-500 mb-1">Alınan (Tahsil Edilen)</div>
                  <div className="text-2xl font-bold text-green-600">{formatCurrency(payments.filter(p => p.tip === 'ogrenci').reduce((s, p) => s + (p.miktar || 0), 0))}</div>
                  <div className="text-xs text-green-600 mt-1">{payments.filter(p => p.tip === 'ogrenci').length} tahsilat</div>
                </CardContent>
              </Card>
              <Card className="border-0 shadow-sm bg-gradient-to-br from-red-50 to-orange-100">
                <CardContent className="p-5 text-center">
                  <div className="text-sm text-red-700 font-medium mb-2">📤 Öğretmen Ücretleri</div>
                  <div className="text-xs text-gray-500 mb-1">Ödenecek</div>
                  <div className="text-2xl font-bold text-red-800">{formatCurrency(teachers.reduce((s, t) => s + (t.yapilmasi_gereken_odeme || 0), 0))}</div>
                  <div className="border-t border-red-200 my-2"></div>
                  <div className="text-xs text-gray-500 mb-1">Ödenen</div>
                  <div className="text-2xl font-bold text-red-600">{formatCurrency(payments.filter(p => p.tip === 'ogretmen').reduce((s, p) => s + (p.miktar || 0), 0))}</div>
                  <div className="text-xs text-red-600 mt-1">{payments.filter(p => p.tip === 'ogretmen').length} ödeme</div>
                </CardContent>
              </Card>
              <Card className="border-0 shadow-sm bg-gradient-to-br from-blue-50 to-indigo-100">
                <CardContent className="p-5 text-center">
                  <div className="text-sm text-blue-700 font-medium mb-2">🏦 Kasa Bakiyesi</div>
                  <div className="text-xs text-gray-500 mb-1">Alınan − Ödenen</div>
                  <div className={`text-3xl font-bold ${(payments.filter(p => p.tip === 'ogrenci').reduce((s, p) => s + (p.miktar || 0), 0) - payments.filter(p => p.tip === 'ogretmen').reduce((s, p) => s + (p.miktar || 0), 0)) >= 0 ? 'text-blue-700' : 'text-red-700'}`}>
                    {formatCurrency(payments.filter(p => p.tip === 'ogrenci').reduce((s, p) => s + (p.miktar || 0), 0) - payments.filter(p => p.tip === 'ogretmen').reduce((s, p) => s + (p.miktar || 0), 0))}
                  </div>
                  <div className="border-t border-blue-200 my-2"></div>
                  <div className="text-xs text-gray-500">Kasada kalan para</div>
                </CardContent>
              </Card>
            </div>

            {/* İki Sütunlu Tablo */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* SOL: Alacaklar (Öğrenci Tahsilatları) */}
              <Card className="border-0 shadow-sm border-t-4" style={{borderTopColor: '#27ae60'}}>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center justify-between">
                    <span className="text-green-700">📥 Alacaklar (Öğrenci Ödemeleri)</span>
                    <button onClick={() => setPaymentForm({...paymentForm, _alacakFormAcik: !paymentForm._alacakFormAcik})}
                      className="text-xs px-3 py-1 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 border border-green-200">
                      {paymentForm._alacakFormAcik ? '✕ Kapat' : '+ Tahsilat Ekle'}
                    </button>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Tahsilat Ekleme Formu */}
                  {paymentForm._alacakFormAcik && (
                    <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-4 space-y-3">
                      <div className="text-sm font-semibold text-green-800">Öğrenci Tahsilatı Kaydet</div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label className="text-xs">Öğrenci</Label>
                          <Select value={paymentForm.kisi_id} onValueChange={v => setPaymentForm({...paymentForm, kisi_id:v, tip:'ogrenci'})}>
                            <SelectTrigger className="h-9"><SelectValue placeholder="Seçin" /></SelectTrigger>
                            <SelectContent position="popper">{students.map(s => <SelectItem key={s.id} value={s.id}>{s.ad} {s.soyad}</SelectItem>)}</SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs">Miktar (₺)</Label>
                          <Input type="number" step="0.01" className="h-9" value={paymentForm.miktar} onChange={e => setPaymentForm({...paymentForm, miktar:parseFloat(e.target.value)||0})} />
                        </div>
                      </div>
                      <div>
                        <Label className="text-xs">Açıklama</Label>
                        <Input className="h-9" value={paymentForm.aciklama} onChange={e => setPaymentForm({...paymentForm, aciklama:e.target.value})} placeholder="Ör: Mart ayı ödemesi" />
                      </div>
                      <Button size="sm" className="w-full bg-green-600 hover:bg-green-700 text-white" disabled={!paymentForm.kisi_id || !paymentForm.miktar}
                        onClick={async () => {
                          try {
                            await axios.post(`${API}/payments`, {tip:'ogrenci', kisi_id:paymentForm.kisi_id, miktar:paymentForm.miktar, aciklama:paymentForm.aciklama});
                            setPaymentForm({tip:'ogrenci',kisi_id:'',miktar:0,aciklama:'',_alacakFormAcik:false,_odemeFormAcik:false});
                            fetchPayments(); fetchStudents(); fetchDashboard();
                            toast({title:"✅ Tahsilat kaydedildi"});
                          } catch(e) { toast({title:"Hata", variant:"destructive"}); }
                        }}>
                        💰 Tahsilatı Kaydet
                      </Button>
                    </div>
                  )}
                  <div className="max-h-96 overflow-y-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs">Tarih</TableHead>
                          <TableHead className="text-xs">Öğrenci</TableHead>
                          <TableHead className="text-xs text-right">Miktar</TableHead>
                          <TableHead className="text-xs">Açıklama</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {payments.filter(p => p.tip === 'ogrenci').length === 0 && (
                          <TableRow><TableCell colSpan={4} className="text-center text-gray-400 py-8">Henüz alacak kaydı yok</TableCell></TableRow>
                        )}
                        {payments.filter(p => p.tip === 'ogrenci').map(p => {
                          const person = students.find(s => s.id === p.kisi_id);
                          return (
                            <TableRow key={p.id}>
                              <TableCell className="text-xs text-gray-500">{formatDate(p.tarih)}</TableCell>
                              <TableCell className="text-sm font-medium">{person ? `${person.ad} ${person.soyad}` : '-'}</TableCell>
                              <TableCell className="text-sm font-bold text-green-600 text-right">{formatCurrency(p.miktar)}</TableCell>
                              <TableCell className="text-xs text-gray-500">{p.aciklama || '-'}</TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                  <div className="border-t-2 border-green-200 mt-3 pt-3 flex justify-between items-center">
                    <span className="text-sm font-semibold text-green-700">Toplam Alacak:</span>
                    <span className="text-lg font-bold text-green-700">{formatCurrency(payments.filter(p => p.tip === 'ogrenci').reduce((s, p) => s + (p.miktar || 0), 0))}</span>
                  </div>
                </CardContent>
              </Card>

              {/* SAĞ: Ödenecekler (Öğretmen Ödemeleri) */}
              <Card className="border-0 shadow-sm border-t-4" style={{borderTopColor: '#e74c3c'}}>
                <CardHeader className="pb-3">
                  <CardTitle className="text-base flex items-center justify-between">
                    <span className="text-red-700">📤 Ödemeler (Öğretmen Ücretleri)</span>
                    <button onClick={() => setPaymentForm({...paymentForm, _odemeFormAcik: !paymentForm._odemeFormAcik})}
                      className="text-xs px-3 py-1 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 border border-red-200">
                      {paymentForm._odemeFormAcik ? '✕ Kapat' : '+ Ödeme Ekle'}
                    </button>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {/* Ödeme Ekleme Formu */}
                  {paymentForm._odemeFormAcik && (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4 space-y-3">
                      <div className="text-sm font-semibold text-red-800">Öğretmen Ödemesi Kaydet</div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <Label className="text-xs">Öğretmen</Label>
                          <Select value={paymentForm.kisi_id} onValueChange={v => setPaymentForm({...paymentForm, kisi_id:v, tip:'ogretmen'})}>
                            <SelectTrigger className="h-9"><SelectValue placeholder="Seçin" /></SelectTrigger>
                            <SelectContent position="popper">{teachers.map(t => <SelectItem key={t.id} value={t.id}>{t.ad} {t.soyad}</SelectItem>)}</SelectContent>
                          </Select>
                        </div>
                        <div>
                          <Label className="text-xs">Miktar (₺)</Label>
                          <Input type="number" step="0.01" className="h-9" value={paymentForm.miktar} onChange={e => setPaymentForm({...paymentForm, miktar:parseFloat(e.target.value)||0})} />
                        </div>
                      </div>
                      <div>
                        <Label className="text-xs">Açıklama</Label>
                        <Input className="h-9" value={paymentForm.aciklama} onChange={e => setPaymentForm({...paymentForm, aciklama:e.target.value})} placeholder="Ör: Mart ayı öğretmen ücreti" />
                      </div>
                      <Button size="sm" className="w-full bg-red-600 hover:bg-red-700 text-white" disabled={!paymentForm.kisi_id || !paymentForm.miktar}
                        onClick={async () => {
                          try {
                            await axios.post(`${API}/payments`, {tip:'ogretmen', kisi_id:paymentForm.kisi_id, miktar:paymentForm.miktar, aciklama:paymentForm.aciklama});
                            setPaymentForm({tip:'ogrenci',kisi_id:'',miktar:0,aciklama:'',_alacakFormAcik:false,_odemeFormAcik:false});
                            fetchPayments(); fetchTeachers(); fetchDashboard();
                            toast({title:"✅ Ödeme kaydedildi"});
                          } catch(e) { toast({title:"Hata", variant:"destructive"}); }
                        }}>
                        💳 Ödemeyi Kaydet
                      </Button>
                    </div>
                  )}
                  <div className="max-h-96 overflow-y-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="text-xs">Tarih</TableHead>
                          <TableHead className="text-xs">Öğretmen</TableHead>
                          <TableHead className="text-xs text-right">Miktar</TableHead>
                          <TableHead className="text-xs">Açıklama</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {payments.filter(p => p.tip === 'ogretmen').length === 0 && (
                          <TableRow><TableCell colSpan={4} className="text-center text-gray-400 py-8">Henüz ödeme kaydı yok</TableCell></TableRow>
                        )}
                        {payments.filter(p => p.tip === 'ogretmen').map(p => {
                          const person = teachers.find(t => t.id === p.kisi_id);
                          return (
                            <TableRow key={p.id}>
                              <TableCell className="text-xs text-gray-500">{formatDate(p.tarih)}</TableCell>
                              <TableCell className="text-sm font-medium">{person ? `${person.ad} ${person.soyad}` : '-'}</TableCell>
                              <TableCell className="text-sm font-bold text-red-600 text-right">{formatCurrency(p.miktar)}</TableCell>
                              <TableCell className="text-xs text-gray-500">{p.aciklama || '-'}</TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  </div>
                  <div className="border-t-2 border-red-200 mt-3 pt-3 flex justify-between items-center">
                    <span className="text-sm font-semibold text-red-700">Toplam Ödenen:</span>
                    <span className="text-lg font-bold text-red-700">{formatCurrency(payments.filter(p => p.tip === 'ogretmen').reduce((s, p) => s + (p.miktar || 0), 0))}</span>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Aylık Özet Tablosu */}
            <Card className="border-0 shadow-sm mt-6">
              <CardHeader className="pb-3">
                <CardTitle className="text-base flex items-center gap-2">📅 Aylık Özet</CardTitle>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow className="bg-gray-50">
                      <TableHead className="font-semibold">Ay</TableHead>
                      <TableHead className="font-semibold text-right text-green-700">Alacak</TableHead>
                      <TableHead className="font-semibold text-right text-red-700">Ödenen</TableHead>
                      <TableHead className="font-semibold text-right text-blue-700">Net</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {(() => {
                      const aylar = {};
                      const ayAd = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"];
                      payments.forEach(p => {
                        const d = new Date(p.tarih);
                        const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
                        if (!aylar[key]) aylar[key] = { alacak: 0, odenecek: 0, yil: d.getFullYear(), ay: d.getMonth() };
                        if (p.tip === 'ogrenci') aylar[key].alacak += (p.miktar || 0);
                        else aylar[key].odenecek += (p.miktar || 0);
                      });
                      const sorted = Object.entries(aylar).sort((a, b) => b[0].localeCompare(a[0]));
                      if (sorted.length === 0) return <TableRow><TableCell colSpan={4} className="text-center text-gray-400 py-6">Henüz kayıt yok</TableCell></TableRow>;
                      return sorted.map(([key, v]) => (
                        <TableRow key={key}>
                          <TableCell className="font-medium">{ayAd[v.ay]} {v.yil}</TableCell>
                          <TableCell className="text-right font-semibold text-green-600">{formatCurrency(v.alacak)}</TableCell>
                          <TableCell className="text-right font-semibold text-red-600">{formatCurrency(v.odenecek)}</TableCell>
                          <TableCell className={`text-right font-bold ${(v.alacak - v.odenecek) >= 0 ? 'text-blue-600' : 'text-red-600'}`}>{formatCurrency(v.alacak - v.odenecek)}</TableCell>
                        </TableRow>
                      ));
                    })()}
                  </TableBody>
                  <tfoot>
                    <tr className="border-t-2 border-gray-300 bg-gray-50">
                      <td className="p-3 font-bold text-gray-800">GENEL TOPLAM</td>
                      <td className="p-3 text-right font-bold text-green-700">{formatCurrency(payments.filter(p => p.tip === 'ogrenci').reduce((s, p) => s + (p.miktar || 0), 0))}</td>
                      <td className="p-3 text-right font-bold text-red-700">{formatCurrency(payments.filter(p => p.tip === 'ogretmen').reduce((s, p) => s + (p.miktar || 0), 0))}</td>
                      <td className={`p-3 text-right font-bold ${(payments.filter(p => p.tip === 'ogrenci').reduce((s, p) => s + (p.miktar || 0), 0) - payments.filter(p => p.tip === 'ogretmen').reduce((s, p) => s + (p.miktar || 0), 0)) >= 0 ? 'text-blue-700' : 'text-red-700'}`}>
                        {formatCurrency(payments.filter(p => p.tip === 'ogrenci').reduce((s, p) => s + (p.miktar || 0), 0) - payments.filter(p => p.tip === 'ogretmen').reduce((s, p) => s + (p.miktar || 0), 0))}
                      </td>
                    </tr>
                  </tfoot>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Users - admin only */}
          {user.role === "admin" && (
            <TabsContent value="users">
              <UserManagement teachers={teachers} />
            </TabsContent>
          )}

          {/* Giris Analizi */}
          <TabsContent value="giris-analizi">
            <GirisAnaliziModul user={user} students={students} teachers={teachers} />
          </TabsContent>

          {/* Gelisim Alani */}
          <TabsContent value="gelisim">
            <GelisimAlani user={user} students={students} teachers={teachers} courses={courses} onTabChange={setActiveTab} />
          </TabsContent>

          {/* Görev Yönetimi */}
          <TabsContent value="gorevler">
            <GorevYonetimi user={user} students={students} teachers={teachers} />
          </TabsContent>

          {/* Mesajlar */}
          <TabsContent value="mesajlar">
            <MesajlarPanel user={user} />
          </TabsContent>

          {/* Ayarlar - Sadece Admin */}
          {user.role === "admin" && (
            <TabsContent value="ayarlar">
              <SistemAyarlari user={user} />
            </TabsContent>
          )}

          {/* ═══ AI MERKEZİ ═══ */}
          <TabsContent value="ai-merkezi">
            <AiMerkezi user={user} />
          </TabsContent>

        </Tabs>

        {/* Edit Dialog */}
        <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle>{editingItem?.type === 'teacher' ? 'Öğretmen Düzenle' : editingItem?.type === 'student' ? 'Öğrenci Düzenle' : 'Kurs Düzenle'}</DialogTitle>
              <DialogDescription>Bilgileri güncelleyin</DialogDescription>
            </DialogHeader>
            {editingItem && <SimpleEditForm item={editingItem} teachers={teachers} courses={availableCourses} classes={availableClasses} onSave={handleEdit} onCancel={() => setEditDialogOpen(false)} />}
          </DialogContent>
        </Dialog>

        {/* Tahsilat / Ödeme Dialog */}
        <Dialog open={!!tahsilatDialog} onOpenChange={() => setTahsilatDialog(null)}>
          <DialogContent className="max-w-md">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                {tahsilatDialog?.tip === 'ogrenci' ? '💰 Öğrenci Tahsilatı' : '💳 Öğretmen Ödemesi'}
              </DialogTitle>
              <DialogDescription>
                {tahsilatDialog?.kisi ? `${tahsilatDialog.kisi.ad} ${tahsilatDialog.kisi.soyad}` : ''}
                {tahsilatDialog?.tip === 'ogrenci' && tahsilatDialog?.kisi?.yapilmasi_gereken_odeme > 0 && (
                  <span className="block mt-1">
                    Toplam borç: <strong>{formatCurrency(tahsilatDialog.kisi.yapilmasi_gereken_odeme)}</strong> — 
                    Ödenen: <strong>{formatCurrency(tahsilatDialog.kisi.yapilan_odeme || 0)}</strong> — 
                    Kalan: <strong className="text-red-600">{formatCurrency(Math.max(0, tahsilatDialog.kisi.yapilmasi_gereken_odeme - (tahsilatDialog.kisi.yapilan_odeme || 0)))}</strong>
                  </span>
                )}
                {tahsilatDialog?.tip === 'ogretmen' && (
                  <span className="block mt-1">
                    Toplam alacak: <strong>{formatCurrency(tahsilatDialog.kisi?.yapilmasi_gereken_odeme || 0)}</strong>
                  </span>
                )}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              <div>
                <Label>Miktar (₺)</Label>
                <Input type="number" step="0.01" autoFocus
                  value={tahsilatDialog?.miktar || ''}
                  onChange={e => setTahsilatDialog({...tahsilatDialog, miktar: parseFloat(e.target.value) || 0})}
                  placeholder="Ör: 500"
                  className="text-lg font-bold text-center mt-1" />
              </div>
              <div>
                <Label>Açıklama</Label>
                <Input
                  value={tahsilatDialog?.aciklama || ''}
                  onChange={e => setTahsilatDialog({...tahsilatDialog, aciklama: e.target.value})}
                  placeholder={tahsilatDialog?.tip === 'ogrenci' ? 'Ör: Mart ayı taksiti' : 'Ör: Mart ayı öğretmen ücreti'}
                  className="mt-1" />
              </div>
              <div className="flex gap-3">
                <Button className={`flex-1 text-white font-bold ${tahsilatDialog?.tip === 'ogrenci' ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'}`}
                  disabled={!tahsilatDialog?.miktar}
                  onClick={async () => {
                    try {
                      await axios.post(`${API}/payments`, {
                        tip: tahsilatDialog.tip,
                        kisi_id: tahsilatDialog.kisi.id,
                        miktar: tahsilatDialog.miktar,
                        aciklama: tahsilatDialog.aciklama || (tahsilatDialog.tip === 'ogrenci' ? `Tahsilat — ${tahsilatDialog.kisi.ad} ${tahsilatDialog.kisi.soyad}` : `Ödeme — ${tahsilatDialog.kisi.ad} ${tahsilatDialog.kisi.soyad}`),
                      });
                      setTahsilatDialog(null);
                      fetchPayments(); fetchStudents(); fetchTeachers(); fetchDashboard();
                      toast({ title: tahsilatDialog.tip === 'ogrenci' ? '✅ Tahsilat kaydedildi' : '✅ Ödeme kaydedildi' });
                    } catch(e) {
                      toast({ title: 'Hata', description: 'Kayıt oluşturulamadı', variant: 'destructive' });
                    }
                  }}>
                  {tahsilatDialog?.tip === 'ogrenci' ? '💰 Tahsilatı Kaydet' : '💳 Ödemeyi Kaydet'}
                </Button>
                <Button variant="outline" className="flex-1" onClick={() => setTahsilatDialog(null)}>İptal</Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>
      <Toaster />
    </div>
  );
}



// ── DASHBOARD: ONAY BEKLEYENLERKarti ──
// ═══════════════════════════════════════════════
// BİLDİRİM ZİLİ — Tüm paneller için ortak
// ═══════════════════════════════════════════════

function BildirimZili({ user }) {
  const { toast } = useToast();
  const [bildirimler, setBildirimler] = useState([]);
  const [okunmamis, setOkunmamis] = useState(0);
  const [acik, setAcik] = useState(false);

  const fetchBildirimler = useCallback(async () => {
    try { const r = await axios.get(`${API}/bildirimler`); setBildirimler(Array.isArray(r.data) ? r.data.slice(0, 20) : []); } catch(e) {}
    try { const r = await axios.get(`${API}/bildirimler/okunmamis`); setOkunmamis(r.data?.sayi || 0); } catch(e) {}
  }, []);

  useEffect(() => { fetchBildirimler(); const iv = setInterval(fetchBildirimler, 30000); return () => clearInterval(iv); }, [fetchBildirimler]);

  const oku = async (id) => { try { await axios.put(`${API}/bildirimler/${id}/okundu`); fetchBildirimler(); } catch(e) {} };
  const tumunuOku = async () => { try { await axios.put(`${API}/bildirimler/tumunu-oku`); fetchBildirimler(); } catch(e) {} };

  const turIkon = { rapor_tamamlandi: "📋", gorev_atandi: "📌", gorev_tamamlandi: "✅", gorev_hatirlatma: "⏰", streak_kirildi: "🔥", streak_tebrik: "🎉", kur_atladi: "🎓", mesaj_geldi: "✉️", rozet_kazandi: "🏅", risk_yuksek: "🚨", anket_hatirlatma: "⭐", lig_yukseldi: "🏆", haftalik_ozet: "📊" };

  return (
    <div className="relative">
      <button onClick={() => setAcik(!acik)} className="relative p-2 rounded-xl hover:bg-gray-100 transition-all">
        <Bell className="h-5 w-5 text-gray-600" />
        {okunmamis > 0 && <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold rounded-full w-5 h-5 flex items-center justify-center">{okunmamis > 9 ? "9+" : okunmamis}</span>}
      </button>
      {acik && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setAcik(false)} />
          <div className="absolute right-0 top-12 w-80 sm:w-96 bg-white rounded-2xl shadow-2xl border z-50 max-h-[70vh] flex flex-col">
            <div className="flex items-center justify-between p-3 border-b">
              <span className="font-bold text-sm">Bildirimler {okunmamis > 0 && `(${okunmamis})`}</span>
              {okunmamis > 0 && <button onClick={tumunuOku} className="text-xs text-blue-600 hover:underline">Tümünü oku</button>}
            </div>
            <div className="overflow-y-auto flex-1">
              {bildirimler.length === 0 ? (
                <div className="p-6 text-center text-gray-400 text-sm">Bildirim yok</div>
              ) : bildirimler.map(b => (
                <div key={b.id} onClick={() => !b.okundu && oku(b.id)}
                  className={`p-3 border-b border-gray-50 cursor-pointer hover:bg-gray-50 transition-all ${!b.okundu ? 'bg-blue-50/50' : ''}`}>
                  <div className="flex items-start gap-2">
                    <span className="text-lg">{turIkon[b.tur] || "🔔"}</span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className={`text-xs font-medium ${!b.okundu ? 'text-blue-700' : 'text-gray-600'}`}>{b.baslik}</span>
                        {!b.okundu && <span className="w-2 h-2 bg-blue-500 rounded-full shrink-0" />}
                      </div>
                      <p className="text-xs text-gray-600 mt-0.5 line-clamp-2">{b.icerik}</p>
                      <span className="text-[10px] text-gray-400">{new Date(b.tarih).toLocaleDateString('tr-TR')} {new Date(b.tarih).toLocaleTimeString('tr-TR', {hour:'2-digit',minute:'2-digit'})}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function BekleyenlerKarti({ bekleyenler, onRefresh, onTabChange }) {
  const { toast } = useToast();
  const [acikDetay, setAcikDetay] = useState(null);

  const adminKararMetin = async (id, onay, direkt = false) => {
    try { await axios.post(`${API}/diagnostic/texts/${id}/admin-karar`, { onay, direkt }); toast({ title: direkt ? "✅ Direkt havuza alındı" : onay ? "🗳️ Oylama başlatıldı" : "❌ Reddedildi" }); onRefresh(); }
    catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };
  const adminKararGelisim = async (id, onay, direkt = false) => {
    try { await axios.post(`${API}/gelisim/icerik/${id}/admin-karar`, { onay, direkt }); toast({ title: direkt ? "✅ Direkt yayına alındı" : onay ? "🗳️ Oylama başlatıldı" : "❌ Reddedildi" }); onRefresh(); }
    catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };
  const adminKararKitap = async (id, onay, direkt = false) => {
    try { await axios.post(`${API}/kitaplar/${id}/admin-karar`, { onay, direkt }); toast({ title: direkt ? "✅ Direkt onaylandı" : onay ? "🗳️ Oylama başlatıldı" : "❌ Reddedildi" }); onRefresh(); }
    catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const turLabel = { hikaye: "Hikaye", bilgilendirici: "Bilgilendirici", siir: "Şiir", hizmetici: "Hizmetiçi", film: "Film", kitap: "Kitap", makale: "Makale" };
  const tipRenk = { metin: "bg-blue-100 text-blue-700", gelisim: "bg-purple-100 text-purple-700", kitap: "bg-green-100 text-green-700" };
  const tipIcon = { metin: "📄", gelisim: "🎓", kitap: "📚" };
  const tipLabel = { metin: "Metin", gelisim: "Gelişim", kitap: "Kitap" };

  const tumListe = [
    ...(bekleyenler.metin_bekleyen || []).map(i => ({ ...i, _tip: "metin" })),
    ...(bekleyenler.gelisim_bekleyen || []).map(i => ({ ...i, _tip: "gelisim" })),
    ...(bekleyenler.kitap_bekleyen || []).map(i => ({ ...i, _tip: "kitap" })),
    ...(bekleyenler.metin_oylama || []).map(i => ({ ...i, _tip: "metin" })),
    ...(bekleyenler.gelisim_oylama || []).map(i => ({ ...i, _tip: "gelisim" })),
    ...(bekleyenler.kitap_oylama || []).map(i => ({ ...i, _tip: "kitap" })),
  ];

  const karar = (item) => {
    if (item._tip === "metin") return { onayla: (d) => adminKararMetin(item.id, true, d), reddet: () => adminKararMetin(item.id, false) };
    if (item._tip === "kitap") return { onayla: (d) => adminKararKitap(item.id, true, d), reddet: () => adminKararKitap(item.id, false) };
    return { onayla: (d) => adminKararGelisim(item.id, true, d), reddet: () => adminKararGelisim(item.id, false) };
  };

  return (
    <Card className="border-2 border-orange-200 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-orange-400 to-red-500 rounded-xl flex items-center justify-center"><span className="text-white font-bold text-sm">{bekleyenler.toplam}</span></div>
            <div><div className="text-base font-bold">Onay Bekleyenler</div>
              <div className="text-xs text-gray-500 font-normal">{(bekleyenler.metin_bekleyen?.length||0) + (bekleyenler.gelisim_bekleyen?.length||0) + (bekleyenler.kitap_bekleyen?.length||0)} karar • {(bekleyenler.metin_oylama?.length||0) + (bekleyenler.gelisim_oylama?.length||0) + (bekleyenler.kitap_oylama?.length||0)} oylama</div></div>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {tumListe.length === 0 ? <p className="text-sm text-gray-500 text-center py-4">Bekleyen içerik yok</p> : (
          <div className="space-y-2">
            {tumListe.map(item => {
              const isBekleyen = item.durum === "beklemede";
              const isAcik = acikDetay === item.id;
              const k = karar(item);
              return (
                <div key={item.id} className={`rounded-xl border overflow-hidden ${isBekleyen ? 'border-yellow-200' : 'border-blue-100'}`}>
                  {/* Başlık satırı - tıklanabilir */}
                  <div className={`flex items-center justify-between p-3 cursor-pointer ${isBekleyen ? 'bg-yellow-50 hover:bg-yellow-100' : 'bg-blue-50 hover:bg-blue-100'} transition-colors`}
                    onClick={() => setAcikDetay(isAcik ? null : item.id)}>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${tipRenk[item._tip]}`}>{tipIcon[item._tip]} {tipLabel[item._tip]}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full ${isBekleyen ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>{isBekleyen ? "⏳ Onay" : `🗳️ ${Object.keys(item.oylar || {}).length} oy`}</span>
                      </div>
                      <div className="font-semibold text-sm text-gray-800 mt-1 truncate">{item.baslik}</div>
                      <div className="text-xs text-gray-500">{item.ekleyen_ad} • {turLabel[item.tur] || item.tur} • {new Date(item.olusturma_tarihi).toLocaleDateString("tr-TR")}</div>
                    </div>
                    <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${isAcik ? 'rotate-180' : ''}`} />
                  </div>

                  {/* Detay - açılır kapanır */}
                  {isAcik && (
                    <div className="p-4 bg-white border-t space-y-3">
                      {/* İçerik detayı */}
                      {item.aciklama && <div className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3 whitespace-pre-wrap">{item.aciklama}</div>}
                      {item._tip === "metin" && item.icerik && <div className="bg-gray-50 rounded-lg p-3 text-sm text-gray-800 max-h-48 overflow-y-auto whitespace-pre-wrap">{item.icerik}</div>}
                      {item._tip === "metin" && (<div className="flex gap-4 text-xs text-gray-500"><span>Sınıf: {item.sinif_seviyesi}</span><span>Tür: {turLabel[item.tur] || item.tur}</span>{item.kelime_sayisi && <span>Kelime: {item.kelime_sayisi}</span>}</div>)}
                      {item._tip === "gelisim" && item.makale_link && <a href={item.makale_link} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline block">📎 {item.makale_dosya_turu === "link" ? "Makale Linki" : "Dosya Linki"}</a>}
                      {item._tip === "gelisim" && item.hedef_kitle && <div className="text-xs text-gray-500">Hedef: {({"hepsi":"Herkes","ogretmen":"Öğretmenler","ogrenci":"Öğrenciler"})[item.hedef_kitle] || item.hedef_kitle}</div>}
                      {item._tip === "kitap" && (<div className="flex gap-4 text-xs text-gray-500">{item.yazar && <span>Yazar: {item.yazar}</span>}{item.yayinevi && <span>Yayınevi: {item.yayinevi}</span>}{item.sayfa_sayisi && <span>Sayfa: {item.sayfa_sayisi}</span>}</div>)}
                      {item.sorular?.length > 0 && (<div className="bg-blue-50 rounded-lg p-3"><div className="text-xs font-medium text-blue-700 mb-2">📝 {item.sorular.length} Test Sorusu</div>{item.sorular.map((s, i) => (<div key={i} className="text-sm text-gray-700 mb-3 pb-3 border-b border-blue-100 last:border-0"><div className="font-medium mb-1">{i+1}. {s.soru}</div><div className="grid grid-cols-2 gap-1 ml-4">{(s.secenekler || []).map((sec, j) => (<div key={j} className={`text-xs px-2 py-1 rounded ${j === s.dogru_cevap ? 'bg-green-100 text-green-700 font-bold' : 'bg-white text-gray-600'}`}>{['A','B','C','D'][j]}) {sec}</div>))}</div></div>))}</div>)}

                      {/* Oylama durumu */}
                      {!isBekleyen && Object.keys(item.oylar || {}).length > 0 && (
                        <div className="bg-gray-50 rounded-lg p-3"><div className="text-xs font-medium text-gray-600 mb-1">Oylar ({Object.keys(item.oylar).length})</div>
                          {Object.entries(item.oylar).map(([uid, oy]) => (<div key={uid} className="text-xs flex items-center gap-2">{oy.onay ? "✅" : "❌"} <span className="text-gray-500">{oy.sebep || "Onayladı"}</span></div>))}
                        </div>
                      )}

                      {/* Karar butonları */}
                      {isBekleyen && (
                        <div className="flex gap-2 pt-2">
                          <Button size="sm" className="bg-green-600 text-white flex-1" onClick={() => k.onayla(true)}>✅ Direkt Onayla</Button>
                          <Button size="sm" className="bg-blue-600 text-white flex-1" onClick={() => k.onayla(false)}>🗳️ Oylamaya Al</Button>
                          <Button size="sm" variant="destructive" className="flex-1" onClick={() => k.reddet()}>❌ Reddet</Button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Sadece havuzdaki metinleri listele (analiz için) ──
function MetinSecimListesi({ onMetinSec }) {
  const [metinler, setMetinler] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(true);
  const turLabel = { hikaye: "Hikaye", bilgilendirici: "Bilgilendirici", siir: "Şiir" };

  useEffect(() => {
    axios.get(`${API}/diagnostic/texts`)
      .then(r => { const d = Array.isArray(r.data) ? r.data : []; setMetinler(d.filter(m => m.durum === "havuzda")); })
      .catch(() => {})
      .finally(() => setYukleniyor(false));
  }, []);

  if (yukleniyor) return <div className="text-center py-8 text-gray-400">Yükleniyor...</div>;
  if (metinler.length === 0) return (
    <div className="text-center py-8 text-gray-400">
      <p>Henüz onaylı metin yok.</p>
      <p className="text-sm mt-1">Metinler sekmesinden metin ekleyip onaylayın.</p>
    </div>
  );

  return (
    <div className="space-y-2 max-h-[50vh] overflow-y-auto pr-1">
      {metinler.map(m => (
        <div key={m.id} onClick={() => onMetinSec(m)}
          className="border border-gray-200 rounded-xl p-4 cursor-pointer hover:border-orange-400 hover:bg-orange-50 transition-all">
          <div className="font-semibold text-gray-800">{m.baslik}</div>
          <div className="text-xs text-gray-500 mt-1">{m.sinif_seviyesi}. Sınıf • {turLabel[m.tur] || m.tur} • {m.kelime_sayisi} kelime</div>
          <p className="text-sm text-gray-600 mt-2 line-clamp-2">{m.icerik}</p>
        </div>
      ))}
    </div>
  );
}

// ── NORM TABLOSU YÖNETİMİ (Admin) ──
function NormTablosu({ onClose }) {
  const { toast } = useToast();
  const [normlar, setNormlar] = useState(null);
  const [loading, setLoading] = useState(true);

  const siniflar = ["1","2","3","4","5","6","7","8"];

  useEffect(() => {
    axios.get(`${API}/diagnostic/normlar`).then(r => {
      setNormlar(r.data);
      setLoading(false);
    });
  }, []);

  const kaydet = async () => {
    try {
      await axios.put(`${API}/diagnostic/normlar`, { normlar });
      toast({ title: "Norm tablosu güncellendi" });
      onClose();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  if (loading || !normlar) return <div className="p-8 text-center text-gray-500">Yükleniyor...</div>;

  return (
    <div className="space-y-4">
      <p className="text-sm text-gray-600">Her sınıf için okuma hızı sınır değerlerini kelime/dakika cinsinden girin.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-gray-100">
              <th className="p-3 text-left font-semibold border border-gray-200">Sınıf</th>
              <th className="p-3 text-center font-semibold border border-gray-200 text-red-600">Düşük (≤)</th>
              <th className="p-3 text-center font-semibold border border-gray-200 text-yellow-600">Orta (≤)</th>
              <th className="p-3 text-center font-semibold border border-gray-200 text-blue-600">Yeterli (≤)</th>
              <th className="p-3 text-center font-semibold border border-gray-200 text-green-600">İleri (&gt;)</th>
            </tr>
          </thead>
          <tbody>
            {siniflar.map(s => {
              const n = normlar[s] || { dusuk: 0, orta: 0, yeterli: 0 };
              return (
                <tr key={s} className="hover:bg-gray-50">
                  <td className="p-3 border border-gray-200 font-medium">{s}. Sınıf</td>
                  {["dusuk","orta","yeterli"].map(alan => (
                    <td key={alan} className="p-2 border border-gray-200">
                      <input type="number" value={n[alan] || ""} min={0} max={500}
                        onChange={e => setNormlar({...normlar, [s]: {...n, [alan]: parseInt(e.target.value)||0}})}
                        className="w-full text-center border border-gray-300 rounded-lg p-2 focus:outline-none focus:ring-2 focus:ring-orange-500" />
                    </td>
                  ))}
                  <td className="p-3 border border-gray-200 text-center text-green-600 font-medium">{(n.yeterli||0)+1}+</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="flex gap-3 pt-2">
        <Button onClick={kaydet} className="flex-1 bg-gradient-to-r from-orange-500 to-red-500 text-white">Kaydet</Button>
        <Button variant="outline" onClick={onClose} className="flex-1">İptal</Button>
      </div>
    </div>
  );
}

// ── METİN YÖNETİMİ (Moderasyon Akışlı) ──
function MetinYonetimi({ onMetinSec, secimModu = false, user }) {
  const { toast } = useToast();
  const [metinler, setMetinler] = useState([]);
  const [formAcik, setFormAcik] = useState(false);
  const [form, setForm] = useState({ baslik: "", icerik: "", kelime_sayisi: 0, sinif_seviyesi: "4", tur: "hikaye" });
  const [redDialog, setRedDialog] = useState(null);
  const [redSebep, setRedSebep] = useState("");
  const [puanAyarlari, setPuanAyarlari] = useState({ metin_ekleme: 5, oylama_katilim: 2, metin_havuza_girme: 10 });
  const [puanDuzenle, setPuanDuzenle] = useState(false);

  const fetchMetinler = async () => {
    try { const r = await axios.get(`${API}/diagnostic/texts`); setMetinler(r.data); } catch(e) {}
  };

  const fetchPuanAyarlari = async () => {
    try { const r = await axios.get(`${API}/ayarlar/puanlar`); setPuanAyarlari(r.data); } catch(e) {}
  };

  useEffect(() => { fetchMetinler(); fetchPuanAyarlari(); }, []);

  const kelimeSay = (t) => t.trim().split(/\s+/).filter(Boolean).length;

  const kaydet = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/diagnostic/texts`, { ...form, kelime_sayisi: kelimeSay(form.icerik) });
      setForm({ baslik: "", icerik: "", kelime_sayisi: 0, sinif_seviyesi: "4", tur: "hikaye" });
      setFormAcik(false); fetchMetinler();
      const rol = user?.role;
      toast({ title: "Metin eklendi (+5 puan)", description: rol === "admin" ? "Oylama başlatıldı" : "Yönetici onayına gönderildi" });
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const sil = async (id) => {
    try { await axios.delete(`${API}/diagnostic/texts/${id}`); fetchMetinler(); toast({ title: "Silindi" }); }
    catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const adminKarar = async (metinId, onay, direkt = false) => {
    try {
      await axios.post(`${API}/diagnostic/texts/${metinId}/admin-karar`, { onay, direkt });
      fetchMetinler();
      toast({ title: direkt ? "✅ Direkt havuza alındı" : onay ? "🗳️ Oylama başlatıldı" : "❌ Reddedildi" });
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const oyVer = async (metinId, onay, sebep = "") => {
    if (!onay && !sebep) { setRedDialog(metinId); return; }
    try {
      const r = await axios.post(`${API}/diagnostic/texts/oy`, { metin_id: metinId, onay, sebep });
      fetchMetinler(); setRedDialog(null); setRedSebep("");
      toast({ title: onay ? "✅ Onaylandı (+2 puan)" : "❌ Reddedildi", description: `Onay oranı: %${r.data.onay_orani}` });
    } catch(e) { console.error('Session error:', e.response?.data); toast({ title: "Hata", description: e.response?.data?.detail, variant: "destructive" }); }
  };

  const turLabel = { hikaye: "Hikaye", bilgilendirici: "Bilgilendirici", siir: "Şiir" };
  const durumBadge = (d) => ({
    beklemede: <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 text-xs rounded-full">⏳ Onay Bekliyor</span>,
    oylama: <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">🗳️ Oylamada</span>,
    havuzda: <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">✅ Havuzda</span>,
    reddedildi: <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full">❌ Reddedildi</span>,
  }[d] || null);

  const oyKullandi = (m) => m.oylar && m.oylar[user?.id];
  const onayOrani = (m) => {
    const oylar = m.oylar || {};
    const t = Object.keys(oylar).length;
    if (!t) return null;
    return Math.round(Object.values(oylar).filter(o => o.onay).length / t * 100);
  };

  // Seçim modunda sadece havuzdakileri göster
  const gorunurMetinler = secimModu ? metinler.filter(m => m.durum === "havuzda") : metinler;
  const bekleyenler = metinler.filter(m => m.durum === "beklemede");
  const oylamadakiler = metinler.filter(m => m.durum === "oylama");

  return (
    <div className="space-y-4">
      {/* Üst bar */}
      <div className="flex items-center justify-between">
        <h3 className="font-semibold text-gray-800">{secimModu ? "Analiz Metinleri" : "Analiz Metinleri"}</h3>
        <Button onClick={() => setFormAcik(!formAcik)} className="bg-gradient-to-r from-orange-500 to-red-500 text-white" size="sm">
          <Plus className="h-4 w-4 mr-1"/>{formAcik ? "İptal" : "Metin Ekle (+5 puan)"}
        </Button>
      </div>

      {/* Metin Ekleme Formu */}
      {formAcik && (
        <Card className="border-2 border-orange-200">
          <CardContent className="p-5">
            <form onSubmit={kaydet} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div><Label>Başlık</Label><Input value={form.baslik} onChange={e => setForm({...form, baslik: e.target.value})} required /></div>
                <div><Label>Sınıf Seviyesi</Label>
                  <Select value={form.sinif_seviyesi} onValueChange={v => setForm({...form, sinif_seviyesi: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{["1","2","3","4","5","6","7","8"].map(s => <SelectItem key={s} value={s}>{s}. Sınıf</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div><Label>Tür</Label>
                <Select value={form.tur} onValueChange={v => setForm({...form, tur: v})}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="hikaye">Hikaye</SelectItem>
                    <SelectItem value="bilgilendirici">Bilgilendirici</SelectItem>
                    <SelectItem value="siir">Şiir</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Metin İçeriği</Label>
                <textarea value={form.icerik} onChange={e => setForm({...form, icerik: e.target.value})} required rows={8}
                  className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 resize-y font-serif leading-relaxed" />
                <p className="text-xs text-gray-500 mt-1">Kelime sayısı: {kelimeSay(form.icerik)}</p>
              </div>
              <div className="flex gap-3">
                <Button type="submit" className="flex-1">Kaydet</Button>
                <Button type="button" variant="outline" onClick={() => setFormAcik(false)} className="flex-1">İptal</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Admin: Onay Bekleyenler */}
      {(user?.role === "admin" || user?.role === "coordinator") && bekleyenler.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-yellow-700 mb-2">⏳ Onay Bekleyenler ({bekleyenler.length})</h4>
          {bekleyenler.map(m => (
            <div key={m.id} className="border-2 border-yellow-200 rounded-xl p-4 mb-2 bg-yellow-50">
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-semibold">{m.baslik}</div>
                  <div className="text-xs text-gray-500">{m.sinif_seviyesi}. Sınıf • {turLabel[m.tur]} • {m.kelime_sayisi} kelime • Ekleyen: {m.ekleyen_ad}</div>
                  <p className="text-sm text-gray-600 mt-1 line-clamp-2">{m.icerik}</p>
                </div>
              </div>
              <div className="flex gap-2 mt-3 flex-wrap">
                <Button size="sm" onClick={() => adminKarar(m.id, true, false)} className="bg-blue-600 hover:bg-blue-700 text-white">🗳️ Oylama Başlat</Button>
                <Button size="sm" onClick={() => adminKarar(m.id, true, true)} className="bg-green-600 hover:bg-green-700 text-white">✅ Direkt Havuza Al</Button>
                <Button size="sm" variant="destructive" onClick={() => adminKarar(m.id, false)}>❌ Reddet</Button>
                <Button size="sm" variant="destructive" onClick={() => sil(m.id)}><Trash2 className="h-4 w-4"/></Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Oylamadakiler */}
      {oylamadakiler.length > 0 && (user?.role === "admin" || user?.role === "teacher") && (
        <div>
          <h4 className="text-sm font-semibold text-blue-700 mb-2">🗳️ Oylamada ({oylamadakiler.length})</h4>
          {oylamadakiler.map(m => {
            const kullandi = oyKullandi(m);
            const oran = onayOrani(m);
            const oyCount = Object.keys(m.oylar || {}).length;
            return (
              <div key={m.id} className="border-2 border-blue-200 rounded-xl p-4 mb-2">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <div className="font-semibold">{m.baslik}</div>
                    <div className="text-xs text-gray-500">{m.sinif_seviyesi}. Sınıf • {turLabel[m.tur]} • {m.kelime_sayisi} kelime • Ekleyen: {m.ekleyen_ad}</div>
                  </div>
                  {oran !== null && <div className="text-right"><div className="text-lg font-bold text-blue-600">%{oran}</div><div className="text-xs text-gray-400">{oyCount} oy</div></div>}
                </div>
                {oran !== null && (
                  <div className="mb-3">
                    <div className="w-full bg-gray-200 rounded-full h-1.5">
                      <div className={`h-1.5 rounded-full ${oran >= 60 ? 'bg-green-500' : 'bg-orange-500'}`} style={{width:`${oran}%`}}></div>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">%60 onay gerekli</p>
                  </div>
                )}
                <p className="text-sm text-gray-600 mb-3 line-clamp-2">{m.icerik}</p>
                {kullandi ? (
                  <div className="text-sm bg-gray-50 p-2 rounded-lg text-gray-500">
                    ✓ Oyunuzu kullandınız: <strong>{kullandi.onay ? "Onay" : "Red"}</strong>
                    {!kullandi.onay && kullandi.sebep && <span> — {kullandi.sebep}</span>}
                  </div>
                ) : (
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => oyVer(m.id, true)} className="bg-green-600 hover:bg-green-700 text-white">✅ Onayla (+2 puan)</Button>
                    <Button size="sm" variant="destructive" onClick={() => { setRedDialog(m.id); }}>❌ Reddet</Button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Havuzdaki / Seçilebilir Metinler */}
      <div className="space-y-2 max-h-80 overflow-y-auto">
        <h4 className="text-sm font-semibold text-green-700 mb-2">✅ Havuzdaki Metinler ({metinler.filter(m => m.durum === "havuzda").length})</h4>
        {metinler.filter(m => m.durum === "havuzda").length === 0 && <p className="text-gray-400 text-sm text-center py-6">Henüz havuzda metin yok. Metin ekleyip onaylayın.</p>}
        {metinler.filter(m => m.durum === "havuzda").map(m => (
          <div key={m.id}
            onClick={() => secimModu && m.durum === "havuzda" && onMetinSec && onMetinSec(m)}
            className={`border rounded-xl p-4 transition-all
              ${secimModu && m.durum === "havuzda" ? 'cursor-pointer hover:border-orange-400 hover:bg-orange-50' : ''}
              ${m.durum === "havuzda" ? 'border-green-200' : 'border-gray-200'}`}>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold">{m.baslik}</span>
                  {durumBadge(m.durum)}
                </div>
                <div className="text-xs text-gray-500 mt-1">{m.sinif_seviyesi}. Sınıf • {turLabel[m.tur]} • {m.kelime_sayisi} kelime</div>
                <p className="text-sm text-gray-600 mt-1 line-clamp-2">{m.icerik}</p>
              </div>
              {(user?.role === "admin" || user?.role === "coordinator") && (
                <Button variant="destructive" size="sm" className="ml-2" onClick={(e) => { e.stopPropagation(); sil(m.id); }}><Trash2 className="h-4 w-4"/></Button>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Puan Rehberi */}
      <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 text-sm">
          <div className="flex items-center justify-between mb-2">
            <div className="font-semibold text-orange-800">🎯 Metin Katkı Puanları</div>
            {(user?.role === "admin" || user?.role === "coordinator") && (
              <button onClick={() => setPuanDuzenle(!puanDuzenle)}
                className="text-xs px-2 py-1 bg-orange-100 text-orange-700 rounded-lg hover:bg-orange-200 border border-orange-300">
                {puanDuzenle ? '✕ Kapat' : '⚙️ Düzenle'}
              </button>
            )}
          </div>
          {!puanDuzenle ? (
            <div className="space-y-1 text-orange-700">
              <div className="flex justify-between"><span>📝 Metin ekle</span><span className="font-bold">+{puanAyarlari.metin_ekleme} puan</span></div>
              <div className="flex justify-between"><span>🗳️ Oylama katıl</span><span className="font-bold">+{puanAyarlari.oylama_katilim} puan</span></div>
              <div className="flex justify-between"><span>🌟 Metin havuza girince</span><span className="font-bold">+{puanAyarlari.metin_havuza_girme} puan</span></div>
            </div>
          ) : (
            <div className="space-y-3 mt-2">
              <div className="flex items-center justify-between gap-3">
                <span className="text-orange-700">📝 Metin ekle</span>
                <input type="number" min="0" value={puanAyarlari.metin_ekleme}
                  onChange={e => setPuanAyarlari({...puanAyarlari, metin_ekleme: parseInt(e.target.value) || 0})}
                  className="w-20 border border-orange-300 rounded-lg p-1 text-center text-sm font-bold focus:outline-none focus:ring-2 focus:ring-orange-400" />
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-orange-700">🗳️ Oylama katıl</span>
                <input type="number" min="0" value={puanAyarlari.oylama_katilim}
                  onChange={e => setPuanAyarlari({...puanAyarlari, oylama_katilim: parseInt(e.target.value) || 0})}
                  className="w-20 border border-orange-300 rounded-lg p-1 text-center text-sm font-bold focus:outline-none focus:ring-2 focus:ring-orange-400" />
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-orange-700">🌟 Metin havuza girince</span>
                <input type="number" min="0" value={puanAyarlari.metin_havuza_girme}
                  onChange={e => setPuanAyarlari({...puanAyarlari, metin_havuza_girme: parseInt(e.target.value) || 0})}
                  className="w-20 border border-orange-300 rounded-lg p-1 text-center text-sm font-bold focus:outline-none focus:ring-2 focus:ring-orange-400" />
              </div>
              <Button size="sm" className="w-full bg-orange-600 hover:bg-orange-700 text-white mt-2"
                onClick={async () => {
                  try {
                    await axios.put(`${API}/ayarlar/puanlar`, puanAyarlari);
                    toast({ title: "✅ Puan ayarları güncellendi" });
                    setPuanDuzenle(false);
                  } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
                }}>
                💾 Kaydet
              </Button>
            </div>
          )}
        </div>

      {/* Red Sebebi Dialog */}
      <Dialog open={!!redDialog} onOpenChange={() => { setRedDialog(null); setRedSebep(""); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>❌ Reddetme Sebebi</DialogTitle>
            <DialogDescription>Bu metni neden reddediyorsunuz?</DialogDescription>
          </DialogHeader>
          <textarea value={redSebep} onChange={e => setRedSebep(e.target.value)} rows={4}
            placeholder="Lütfen sebebinizi açıklayın..."
            className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 resize-none" />
          <div className="flex gap-2">
            <Button variant="destructive" className="flex-1" disabled={!redSebep.trim()} onClick={() => oyVer(redDialog, false, redSebep)}>Reddet</Button>
            <Button variant="outline" className="flex-1" onClick={() => { setRedDialog(null); setRedSebep(""); }}>İptal</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── CANLI ANALİZ EKRANI ──
// user.role === "student" → tam ekran metin (salt okunur)
// user.role === "teacher"/"admin" → üstte rapor formu, altta metin + kontroller
function CanlıAnalizEkrani({ ogrenci, metin, oturumId, onTamamla, user }) {
  const [sure, setSure] = useState(0);
  const [calisıyor, setCalisıyor] = useState(false);
  const [hatalar, setHatalar] = useState([]);
  const [gozlemNotu, setGozlemNotu] = useState("");
  const intervalRef = useRef(null);

  // Rapor form state (öğretmen için)
  const [anlama, setAnlama] = useState({
    cumle_anlama:"orta", bilinmeyen_sozcuk:"orta", baglac_zamir:"orta",
    ana_fikir:"orta", yardimci_fikir:"orta", konu:"orta", baslik_onerme:"orta",
    neden_sonuc:"orta", cikarim:"orta", ipuclari:"orta", yorumlama:"orta",
    gorus_bildirme:"orta", yazar_amaci:"orta", alternatif_fikir:"orta", guncelle_hayat:"orta",
    bilgi:"iyi", kavrama:"iyi", uygulama:"iyi", analiz:"iyi", sentez:"iyi", degerlendirme:"iyi",
    genel_yuzde: 0,
  });
  const [prozodik, setProzodik] = useState({ noktalama:3, vurgu:3, tonlama:3, akicilik:3, anlamli_gruplama:3 });
  const [ogretmenNotu, setOgretmenNotu] = useState("");
  const [kurKarari, setKurKarari] = useState("");
  const [raporAdim, setRaporAdim] = useState(0); // 0=analiz, 1=anlama, 2=prozodik, 3=kur+bitir

  useEffect(() => () => clearInterval(intervalRef.current), []);

  const toggleSayac = () => {
    if (calisıyor) { clearInterval(intervalRef.current); setCalisıyor(false); }
    else { intervalRef.current = setInterval(() => setSure(s => s + 1), 1000); setCalisıyor(true); }
  };

  const hataEkle = (tip) => setHatalar(h => [...h, { tip, kelime: "" }]);
  const hataGeriAl = (tip) => setHatalar(h => { const idx = [...h].map(x=>x.tip).lastIndexOf(tip); return idx>=0 ? [...h.slice(0,idx), ...h.slice(idx+1)] : h; });
  const hataSay = (tip) => hatalar.filter(h => h.tip === tip).length;

  const formatSure = (s) => `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
  const prozodikToplam = Object.values(prozodik).reduce((a,b) => a+b, 0);

  const isOgretmen = user?.role === "admin" || user?.role === "coordinator" || user?.role === "teacher";

  const tamamla = () => {
    if (sure === 0) return;
    clearInterval(intervalRef.current);
    setCalisıyor(false);
    onTamamla({ sure_saniye: sure, hatalar, gozlem_notu: gozlemNotu, anlama, prozodik, ogretmen_notu: ogretmenNotu, ogretmen_kur: kurKarari });
  };

  const hataRenk = { atlama:"bg-red-100 text-red-700 border-red-200", yanlis_okuma:"bg-orange-100 text-orange-700 border-orange-200", takilma:"bg-yellow-100 text-yellow-700 border-yellow-200", tekrar:"bg-purple-100 text-purple-700 border-purple-200" };
  const hataTipler = [
    { tip:"atlama", etiket:"Atlama" },
    { tip:"yanlis_okuma", etiket:"Yanlış Okuma" },
    { tip:"takilma", etiket:"Takılma" },
    { tip:"tekrar", etiket:"Tekrar" },
  ];

  const SeviyeSecici = ({ alan, etiket, state, setState }) => {
    const sevRenk = { zayif:"border-red-300 bg-red-50 text-red-700", orta:"border-yellow-300 bg-yellow-50 text-yellow-700", iyi:"border-green-300 bg-green-50 text-green-700" };
    return (
      <div className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
        <span className="text-xs text-gray-700 flex-1">{etiket}</span>
        <div className="flex gap-1">
          {["zayif","orta","iyi"].map(s => (
            <button key={s} onClick={() => setState({...state, [alan]: s})}
              className={`px-2 py-0.5 rounded text-xs border transition-all ${state[alan]===s ? sevRenk[s] : 'border-gray-200 text-gray-400 hover:bg-gray-50'}`}>
              {s==="zayif"?"Zayıf":s==="orta"?"Orta":"İyi"}
            </button>
          ))}
        </div>
      </div>
    );
  };

  // ── ÖĞRENCİ: Tam ekran metin ──
  if (!isOgretmen) {
    return (
      <div className="fixed inset-0 bg-amber-50 z-50 overflow-auto">
        <div className="max-w-3xl mx-auto p-8">
          <div className="text-center mb-6">
            <h2 className="text-2xl font-bold text-gray-800">{metin.baslik}</h2>
            <p className="text-sm text-gray-500">{metin.sinif_seviyesi}. Sınıf • {metin.kelime_sayisi} kelime</p>
          </div>
          <div className="bg-white rounded-2xl shadow-sm p-8 font-serif text-lg leading-loose text-gray-800 whitespace-pre-wrap">
            {metin.icerik}
          </div>
        </div>
      </div>
    );
  }

  // ── ÖĞRETMEN/ADMİN: Bölünmüş ekran ──
  return (
    <div className="fixed inset-0 bg-gray-100 z-50 flex flex-col overflow-hidden">
      {/* Üst bar */}
      <div className="bg-white border-b px-4 py-2 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-4">
          <span className="font-semibold text-gray-800">{ogrenci.ad} {ogrenci.soyad}</span>
          <span className="text-sm text-gray-500">{metin.baslik} • {metin.kelime_sayisi} kelime</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-3xl font-mono font-bold text-gray-800 tabular-nums">{formatSure(sure)}</div>
          <button onClick={toggleSayac}
            className={`px-4 py-2 rounded-xl text-white font-medium transition-all ${calisıyor ? 'bg-red-500 hover:bg-red-600' : 'bg-green-500 hover:bg-green-600'}`}>
            {calisıyor ? "⏸ Durdur" : "▶ Başlat"}
          </button>
        </div>
      </div>

      {/* Ana içerik: sol metin, sağ panel */}
      <div className="flex flex-1 overflow-hidden">

        {/* Sol: Metin */}
        <div className="flex-1 overflow-y-auto bg-amber-50 p-6">
          <h3 className="text-xl font-bold text-gray-800 mb-4 text-center">{metin.baslik}</h3>
          <div className="font-serif text-base leading-loose text-gray-800 whitespace-pre-wrap max-w-xl mx-auto">
            {metin.icerik}
          </div>
        </div>

        {/* Sağ panel: sekmeli form */}
        <div className="w-96 bg-white border-l overflow-y-auto flex flex-col">
          {/* Adım sekmeleri */}
          <div className="flex border-b shrink-0">
            {["Hata Takibi","Anlama","Prozodik","Kur & Bitir"].map((label, i) => (
              <button key={i} onClick={() => setRaporAdim(i)}
                className={`flex-1 py-2 text-xs font-medium transition-all ${raporAdim===i ? 'border-b-2 border-orange-500 text-orange-600' : 'text-gray-400 hover:text-gray-600'}`}>
                {label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto p-4">

            {/* Adım 0: Hata Takibi */}
            {raporAdim === 0 && (
              <div className="space-y-3">
                {hataTipler.map(({tip, etiket}) => (
                  <div key={tip} className={`flex items-center justify-between p-3 rounded-xl border ${hataRenk[tip]}`}>
                    <span className="font-medium text-sm">{etiket}</span>
                    <div className="flex items-center gap-2">
                      <button onClick={() => hataGeriAl(tip)} className="w-7 h-7 rounded-lg bg-white/60 font-bold text-sm hover:bg-white">−</button>
                      <span className="w-8 text-center font-bold text-lg tabular-nums">{hataSay(tip)}</span>
                      <button onClick={() => hataEkle(tip)} className="w-7 h-7 rounded-lg bg-white/60 font-bold text-sm hover:bg-white">+</button>
                    </div>
                  </div>
                ))}
                <div>
                  <label className="text-xs font-medium text-gray-600">Gözlem Notu</label>
                  <textarea value={gozlemNotu} onChange={e => setGozlemNotu(e.target.value)} rows={3}
                    className="w-full mt-1 border border-gray-200 rounded-xl p-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-orange-400" />
                </div>
              </div>
            )}

            {/* Adım 1: Anlama */}
            {raporAdim === 1 && (
              <div className="space-y-3">
                {[
                  ["4.1 Sözcük Düzeyi", [["cumle_anlama","Cümle anlamı"],["bilinmeyen_sozcuk","Bilinmeyen sözcük"],["baglac_zamir","Bağlaç/zamir"]]],
                  ["4.2 Ana Yapı", [["ana_fikir","Ana fikir"],["yardimci_fikir","Yardımcı fikir"],["konu","Konu"],["baslik_onerme","Başlık önerme"]]],
                  ["4.3 Derin Anlama", [["neden_sonuc","Neden-sonuç"],["cikarim","Çıkarım"],["ipuclari","İpuçları"],["yorumlama","Yorumlama"]]],
                  ["4.4 Eleştirel", [["gorus_bildirme","Görüş bildirme"],["yazar_amaci","Yazar amacı"],["alternatif_fikir","Alternatif fikir"],["guncelle_hayat","Günlük hayat"]]],
                  ["4.5 Soru Performansı", [["bilgi","Bilgi"],["kavrama","Kavrama"],["uygulama","Uygulama"],["analiz","Analiz"],["sentez","Sentez"],["degerlendirme","Değerlendirme"]]],
                ].map(([baslik, alanlar]) => (
                  <div key={baslik}>
                    <div className="text-xs font-semibold text-gray-500 bg-gray-50 px-2 py-1 rounded mb-1">{baslik}</div>
                    {alanlar.map(([alan, etiket]) => (
                      <SeviyeSecici key={alan} alan={alan} etiket={etiket} state={anlama} setState={setAnlama} />
                    ))}
                  </div>
                ))}
                <div className="bg-blue-50 border border-blue-200 rounded-xl p-3">
                  <label className="text-xs font-medium text-blue-700">Genel Anlama % (0 = otomatik)</label>
                  <input type="number" min="0" max="100" value={anlama.genel_yuzde}
                    onChange={e => setAnlama({...anlama, genel_yuzde: parseInt(e.target.value)||0})}
                    className="w-full mt-1 border border-blue-200 rounded-lg p-2 text-center text-lg font-bold focus:outline-none" />
                </div>
              </div>
            )}

            {/* Adım 2: Prozodik */}
            {raporAdim === 2 && (
              <div className="space-y-3">
                {[
                  ["noktalama","Noktalama/Duraklama",["Uymuyor","Kısmen","Çoğunlukla","Tam/bilinçli"]],
                  ["vurgu","Vurgu",["Tek düze","Yer yer","Anlama uygun","Etkili/bilinçli"]],
                  ["tonlama","Tonlama",["Monoton","Sınırlı","Metne uygun","Doğal/etkileyici"]],
                  ["akicilik","Akıcılık",["Sık duraklama","Kısmi akış","Genel akıcı","Kesintisiz"]],
                  ["anlamli_gruplama","Anlamlı Gruplama",["Sözcük sözcük","Kısmen","Çoğunlukla","Tam/tutarlı"]],
                ].map(([alan, etiket, aciklamalar]) => (
                  <div key={alan} className="border border-gray-100 rounded-xl p-3">
                    <div className="text-xs font-semibold text-gray-700 mb-2">{etiket}</div>
                    <div className="grid grid-cols-4 gap-1">
                      {[1,2,3,4].map(p => (
                        <button key={p} onClick={() => setProzodik({...prozodik, [alan]: p})}
                          className={`p-1.5 rounded-lg text-xs border text-center transition-all ${prozodik[alan]===p ? 'border-orange-400 bg-orange-50 text-orange-700 font-bold' : 'border-gray-200 text-gray-400 hover:bg-gray-50'}`}>
                          <div className="font-bold">{p}</div>
                          <div className="text-[10px] leading-tight">{aciklamalar[p-1]}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
                <div className="bg-orange-50 border border-orange-200 rounded-xl p-3 text-center">
                  <div className="text-sm text-orange-700 font-medium">Toplam: <span className="text-2xl font-bold">{prozodikToplam}</span>/20</div>
                </div>
              </div>
            )}

            {/* Adım 3: Kur & Bitir */}
            {raporAdim === 3 && (
              <div className="space-y-4">
                <div>
                  <label className="text-xs font-medium text-gray-600">Öğretmen Notu</label>
                  <textarea value={ogretmenNotu} onChange={e => setOgretmenNotu(e.target.value)} rows={4}
                    placeholder="Genel değerlendirme ve öneriler..."
                    className="w-full mt-1 border border-gray-200 rounded-xl p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-orange-400" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-600">Kur Kararı</label>
                  <div className="grid grid-cols-3 gap-2 mt-2">
                    {["Kur 1","Kur 2","Kur 3"].map(k => (
                      <button key={k} onClick={() => setKurKarari(k)}
                        className={`py-3 rounded-xl border-2 font-bold text-sm transition-all ${kurKarari===k ? 'border-orange-500 bg-orange-50 text-orange-700' : 'border-gray-200 text-gray-500 hover:border-orange-300'}`}>
                        {k}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="text-xs text-gray-500 bg-gray-50 rounded-xl p-3 space-y-1">
                  <div>⏱ Süre: <strong>{formatSure(sure)}</strong></div>
                  <div>❌ Toplam hata: <strong>{hatalar.length}</strong></div>
                  <div>📊 Prozodik: <strong>{prozodikToplam}/20</strong></div>
                </div>
                <button onClick={tamamla} disabled={sure===0 || !kurKarari}
                  className="w-full py-4 bg-gradient-to-r from-orange-500 to-red-500 text-white font-bold rounded-xl disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition-all">
                  {sure===0 ? "Önce süre sayacını başlatın" : !kurKarari ? "Kur kararı seçin" : "✅ Analizi Tamamla ve Raporu Oluştur"}
                </button>
              </div>
            )}
          </div>

          {/* Alt navigasyon */}
          <div className="flex border-t p-3 gap-2 shrink-0">
            <button onClick={() => setRaporAdim(a => Math.max(0, a-1))} disabled={raporAdim===0}
              className="flex-1 py-2 text-sm border border-gray-200 rounded-xl disabled:opacity-30 hover:bg-gray-50">← Geri</button>
            <button onClick={() => setRaporAdim(a => Math.min(3, a+1))} disabled={raporAdim===3}
              className="flex-1 py-2 text-sm bg-orange-500 text-white rounded-xl disabled:opacity-30 hover:bg-orange-600">İleri →</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── ANALİZ SONUÇ EKRANI ──
function AnalizSonucEkrani({ sonuc, ogrenci, onKaydet, onYeniAnaliz }) {
  const [ogretmenKur, setOgretmenKur] = useState(sonuc.sistem_kur || sonuc.atanan_kur || "Kur 1");

  const hizRenk = { dusuk: "text-red-600", orta: "text-yellow-600", yeterli: "text-blue-600", ileri: "text-green-600" };
  const hizLabel = { dusuk: "Düşük", orta: "Orta", yeterli: "Yeterli", ileri: "İleri" };

  const formatSure = (s) => `${Math.floor(s/60)}:${Math.round(s%60).toString().padStart(2,'0')}`;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-gray-900">Analiz Sonucu</h2>
        <p className="text-gray-500">{ogrenci.ad} {ogrenci.soyad}</p>
      </div>

      {/* Temel İstatistikler */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="border-0 shadow-sm text-center">
          <CardContent className="p-5">
            <div className="text-3xl font-bold text-blue-600">{sonuc.wpm}</div>
            <div className="text-xs text-gray-500 mt-1">kelime/dakika</div>
            <div className={`text-sm font-medium mt-1 ${hizRenk[sonuc.hiz_deger]}`}>{hizLabel[sonuc.hiz_deger]}</div>
          </CardContent>
        </Card>
        <Card className="border-0 shadow-sm text-center">
          <CardContent className="p-5">
            <div className="text-3xl font-bold text-green-600">%{sonuc.dogruluk_yuzde}</div>
            <div className="text-xs text-gray-500 mt-1">doğruluk oranı</div>
            <div className="text-sm font-medium mt-1 text-gray-600">{sonuc.hata_sayilari ? Object.values(sonuc.hata_sayilari).reduce((a,b)=>a+b,0) : 0} hata</div>
          </CardContent>
        </Card>
        <Card className="border-0 shadow-sm text-center">
          <CardContent className="p-5">
            <div className="text-3xl font-bold text-orange-600">{formatSure(sonuc.sure_saniye)}</div>
            <div className="text-xs text-gray-500 mt-1">okuma süresi</div>
          </CardContent>
        </Card>
      </div>

      {/* Hata Dağılımı */}
      {sonuc.hata_sayilari && (
        <Card className="border-0 shadow-sm">
          <CardHeader><CardTitle className="text-base">Hata Dağılımı</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-3">
              {[["atlama","Atlama","red"],["yanlis_okuma","Yanlış Okuma","orange"],["takilma","Takılma","yellow"],["tekrar","Tekrar","purple"]].map(([key,label,color]) => (
                <div key={key} className={`flex items-center justify-between p-3 bg-${color}-50 rounded-xl border border-${color}-200`}>
                  <span className="text-sm font-medium">{label}</span>
                  <span className={`text-lg font-bold text-${color}-600`}>{sonuc.hata_sayilari[key] || 0}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Kur Kararı */}
      <Card className="border-2 border-orange-200 shadow-sm">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm text-gray-500">Sistem Önerisi</div>
              <div className="text-2xl font-bold text-orange-600">{sonuc.sistem_kur}</div>
            </div>
            <div className="text-4xl">🎯</div>
          </div>
          <div>
            <Label>Öğretmen Kararı</Label>
            <Select value={ogretmenKur} onValueChange={setOgretmenKur}>
              <SelectTrigger className="mt-1"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Kur 1">Kur 1</SelectItem>
                <SelectItem value="Kur 2">Kur 2</SelectItem>
                <SelectItem value="Kur 3">Kur 3</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button onClick={() => onKaydet(ogretmenKur)}
            className="w-full mt-4 bg-gradient-to-r from-orange-500 to-red-500 text-white font-bold py-3">
            ✅ Onayla ve Kaydet
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}


// ── RAPOR FORMU (AI Destekli, Ölçüt Eklenebilir, Yorum Düzenlenebilir) ──
// ══════════════════════════════════════════════
// RaporFormu — AI Destekli, Ölçüt Eklenebilir, Yorum Düzenlenebilir
// Bu fonksiyonu App.js'deki eski RaporFormu ile değiştirin
// ══════════════════════════════════════════════

function RaporFormu({ oturum, sonuc, ogrenci, metin, onRaporTamamla }) {
  const { toast } = useToast();

  const seviyeler = ["zayif", "orta", "iyi"];
  const seviyeLabel = { zayif: "Zayıf", orta: "Orta", iyi: "İyi" };
  const seviyeRenk = {
    zayif: "border-red-300 bg-red-50 text-red-700",
    orta:  "border-yellow-300 bg-yellow-50 text-yellow-700",
    iyi:   "border-green-300 bg-green-50 text-green-700",
  };

  // ── State ──
  const [anlama, setAnlama] = useState({
    cumle_anlama: "orta", bilinmeyen_sozcuk: "orta", baglac_zamir: "orta",
    ana_fikir: "orta", yardimci_fikir: "orta", konu: "orta", baslik_onerme: "orta",
    neden_sonuc: "orta", cikarim: "orta", ipuclari: "orta", yorumlama: "orta",
    gorus_bildirme: "orta", yazar_amaci: "orta", alternatif_fikir: "orta", guncelle_hayat: "orta",
    bilgi: "iyi", kavrama: "iyi", uygulama: "iyi", analiz: "iyi", sentez: "iyi", degerlendirme: "iyi",
    genel_yuzde: 0,
  });
  const [prozodik, setProzodik] = useState({ noktalama: 3, vurgu: 3, tonlama: 3, akicilik: 3, anlamli_gruplama: 3 });
  const [ogretmenNotu, setOgretmenNotu] = useState("");

  // ★ Ek ölçütler (el ile eklenen)
  const [ekAnlamaOlcutleri, setEkAnlamaOlcutleri] = useState([]); // [{id, etiket, kategori, value}]
  const [ekProzodikOlcutleri, setEkProzodikOlcutleri] = useState([]); // [{id, etiket, aciklamalar, puan}]
  const [yeniAnlamaAdi, setYeniAnlamaAdi] = useState("");
  const [yeniAnlamaKat, setYeniAnlamaKat] = useState("sozcuk");
  const [yeniProzodikAdi, setYeniProzodikAdi] = useState("");
  const [anlamaEkleAcik, setAnlamaEkleAcik] = useState(false);
  const [prozodikEkleAcik, setProzodikEkleAcik] = useState(false);

  // ★ AI yorumları (her bölüm için)
  const [aiYorumlar, setAiYorumlar] = useState({
    hiz: "",
    dogruluk: "",
    anlama: "",
    prozodik: "",
    sonuc: "",
    oneriler: "",
  });
  const [aiYukleniyor, setAiYukleniyor] = useState(false);
  const [aiOlusturuldu, setAiOlusturuldu] = useState(false);

  const prozodikToplam = Object.values(prozodik).reduce((a, b) => a + b, 0)
    + ekProzodikOlcutleri.reduce((a, b) => a + (b.puan || 0), 0);

  const anlamaKategoriler = {
    sozcuk: "4.1 Sözcük Düzeyinde Anlama",
    ana_yapi: "4.2 Metnin Ana Yapısını Anlama",
    derin: "4.3 Metinler Arasılık ve Derin Anlama",
    elestirel: "4.4 Eleştirel ve Yaratıcı Okuma",
    soru: "4.5 Soru Performans Analizi",
  };

  // ── Anlama seviye seçici ──
  const SeviyeSecici = ({ alan, etiket, isEk, ekId }) => (
    <div className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
      <span className="text-sm text-gray-700 flex-1">{etiket}</span>
      <div className="flex gap-1 items-center">
        {seviyeler.map(s => (
          <button key={s} onClick={() => {
            if (isEk) {
              setEkAnlamaOlcutleri(prev => prev.map(o => o.id === ekId ? {...o, value: s} : o));
            } else {
              setAnlama({ ...anlama, [alan]: s });
            }
          }}
            className={`px-3 py-1 rounded-lg text-xs font-medium border transition-all ${
              (isEk ? ekAnlamaOlcutleri.find(o=>o.id===ekId)?.value : anlama[alan]) === s
                ? seviyeRenk[s]
                : 'border-gray-200 bg-white text-gray-500 hover:bg-gray-50'
            }`}>
            {seviyeLabel[s]}
          </button>
        ))}
        {isEk && (
          <button onClick={() => setEkAnlamaOlcutleri(prev => prev.filter(o => o.id !== ekId))}
            className="ml-2 text-red-400 hover:text-red-600 text-xs">✕</button>
        )}
      </div>
    </div>
  );

  // ── Prozodik satır ──
  const ProzodikSatir = ({ alan, etiket, aciklama1, aciklama2, aciklama3, aciklama4, isEk, ekId }) => (
    <div className="py-3 border-b border-gray-100 last:border-0">
      <div className="flex items-center justify-between">
        <div className="font-medium text-sm text-gray-800 mb-2">{etiket}</div>
        {isEk && (
          <button onClick={() => setEkProzodikOlcutleri(prev => prev.filter(o => o.id !== ekId))}
            className="text-red-400 hover:text-red-600 text-xs mb-2">✕ Kaldır</button>
        )}
      </div>
      <div className="grid grid-cols-4 gap-1">
        {[1,2,3,4].map(p => (
          <button key={p} onClick={() => {
            if (isEk) {
              setEkProzodikOlcutleri(prev => prev.map(o => o.id === ekId ? {...o, puan: p} : o));
            } else {
              setProzodik({ ...prozodik, [alan]: p });
            }
          }}
            className={`p-2 rounded-lg text-xs border text-center transition-all leading-tight ${
              (isEk ? ekProzodikOlcutleri.find(o=>o.id===ekId)?.puan : prozodik[alan]) === p
                ? 'border-orange-400 bg-orange-50 text-orange-700 font-medium'
                : 'border-gray-200 bg-white text-gray-500 hover:bg-gray-50'
            }`}>
            <div className="font-bold text-sm mb-1">{p} puan</div>
            <div>{[aciklama1, aciklama2, aciklama3, aciklama4][p-1]}</div>
          </button>
        ))}
      </div>
    </div>
  );

  // ── Ölçüt ekleme ──
  const anlamaOlcutEkle = () => {
    if (!yeniAnlamaAdi.trim()) return;
    const id = `ek_${Date.now()}`;
    setEkAnlamaOlcutleri(prev => [...prev, { id, etiket: yeniAnlamaAdi.trim(), kategori: yeniAnlamaKat, value: "orta" }]);
    setYeniAnlamaAdi("");
    setAnlamaEkleAcik(false);
  };

  const prozodikOlcutEkle = () => {
    if (!yeniProzodikAdi.trim()) return;
    const id = `ekp_${Date.now()}`;
    setEkProzodikOlcutleri(prev => [...prev, {
      id, etiket: yeniProzodikAdi.trim(),
      aciklamalar: ["Yetersiz", "Kısmen yeterli", "Yeterli", "Çok iyi"],
      puan: 3,
    }]);
    setYeniProzodikAdi("");
    setProzodikEkleAcik(false);
  };

  // ══════════════════════════════════════════
  // ★★★ AI YORUM OLUŞTURMA ★★★
  // ══════════════════════════════════════════
  const aiYorumlariOlustur = async () => {
    setAiYukleniyor(true);
    try {
      const hizSev = { dusuk: "düşük", orta: "orta", yeterli: "yeterli", ileri: "ileri" }[sonuc?.hiz_deger] || "orta";
      const prozSev = prozodikToplam >= 18 ? "çok iyi" : prozodikToplam >= 14 ? "iyi" : prozodikToplam >= 10 ? "orta" : "geliştirilmeli";
      const anlamaSev = (anlama.genel_yuzde || hesaplaAnlamaYuzde()) >= 85 ? "iyi" : (anlama.genel_yuzde || hesaplaAnlamaYuzde()) >= 70 ? "orta" : "zayıf";

      const ekAnlamaStr = ekAnlamaOlcutleri.length > 0
        ? `\nEk ölçütler: ${ekAnlamaOlcutleri.map(o => `${o.etiket}: ${seviyeLabel[o.value]}`).join(", ")}`
        : "";

      const ekProzodikStr = ekProzodikOlcutleri.length > 0
        ? `\nEk prozodik ölçütler: ${ekProzodikOlcutleri.map(o => `${o.etiket}: ${o.puan}/4`).join(", ")}`
        : "";

      const prompt = `Sen bir okuma becerileri uzmanısın. Aşağıdaki verilere göre her bölüm için profesyonel değerlendirme metni yaz. Türkçe yaz, akademik ama anlaşılır bir dil kullan.

ÖĞRENCİ: ${ogrenci?.ad || ""} ${ogrenci?.soyad || ""}, Sınıf: ${ogrenci?.sinif || ""}
METİN: ${metin?.baslik || ""} (${metin?.kelime_sayisi || 0} kelime, Tür: ${metin?.tur || ""})

VERİLER:
- Okuma Hızı: ${sonuc?.wpm || 0} kelime/dk (${hizSev} düzey)
- Doğruluk: %${sonuc?.dogruluk_yuzde || 0}
- Hata dağılımı: Atlama: ${sonuc?.hata_sayilari?.atlama || 0}, Yanlış okuma: ${sonuc?.hata_sayilari?.yanlis_okuma || 0}, Takılma: ${sonuc?.hata_sayilari?.takilma || 0}, Tekrar: ${sonuc?.hata_sayilari?.tekrar || 0}
- Anlama yüzdesi: %${anlama.genel_yuzde || hesaplaAnlamaYuzde()} (${anlamaSev})
- Anlama detay: Cümle anlama: ${seviyeLabel[anlama.cumle_anlama]}, Bilinmeyen sözcük: ${seviyeLabel[anlama.bilinmeyen_sozcuk]}, Bağlaç/zamir: ${seviyeLabel[anlama.baglac_zamir]}, Ana fikir: ${seviyeLabel[anlama.ana_fikir]}, Yardımcı fikir: ${seviyeLabel[anlama.yardimci_fikir]}, Konu: ${seviyeLabel[anlama.konu]}, Başlık önerme: ${seviyeLabel[anlama.baslik_onerme]}, Neden-sonuç: ${seviyeLabel[anlama.neden_sonuc]}, Çıkarım: ${seviyeLabel[anlama.cikarim]}, İpuçları: ${seviyeLabel[anlama.ipuclari]}, Yorumlama: ${seviyeLabel[anlama.yorumlama]}, Görüş bildirme: ${seviyeLabel[anlama.gorus_bildirme]}, Yazar amacı: ${seviyeLabel[anlama.yazar_amaci]}, Alternatif fikir: ${seviyeLabel[anlama.alternatif_fikir]}, Günlük hayat: ${seviyeLabel[anlama.guncelle_hayat]}${ekAnlamaStr}
- Prozodik toplam: ${prozodikToplam}/20 (${prozSev}), Noktalama: ${prozodik.noktalama}/4, Vurgu: ${prozodik.vurgu}/4, Tonlama: ${prozodik.tonlama}/4, Akıcılık: ${prozodik.akicilik}/4, Anlamlı gruplama: ${prozodik.anlamli_gruplama}/4${ekProzodikStr}
- Önerilen kur: ${sonuc?.atanan_kur || sonuc?.sistem_kur || ""}

JSON formatında yanıt ver (sadece JSON, başka bir şey yazma):
{
  "hiz": "Okuma hızı değerlendirmesi (2-3 cümle)",
  "dogruluk": "Doğru okuma oranı ve hata analizi değerlendirmesi (3-4 cümle)",
  "anlama": "Okuduğunu anlama becerileri genel değerlendirmesi (4-5 cümle, alt boyutlara değin)",
  "prozodik": "Prozodik okuma değerlendirmesi (2-3 cümle)",
  "sonuc": "Sonuç ve genel yorum (4-5 cümle, tüm boyutları birlikte değerlendir)",
  "oneriler": "Eğitsel ve ev temelli gelişim önerileri (6-8 cümle, okul ve ev için ayrı öneriler)"
}`;

      const response = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 1000,
          messages: [{ role: "user", content: prompt }],
        }),
      });

      const data = await response.json();
      const text = data.content?.map(c => c.text || "").join("") || "";
      const cleaned = text.replace(/```json|```/g, "").trim();
      const parsed = JSON.parse(cleaned);

      setAiYorumlar(parsed);
      setAiOlusturuldu(true);
      toast({ title: "✅ AI yorumları oluşturuldu!", description: "İnceleyip düzenleyebilirsiniz." });
    } catch (err) {
      console.error("AI yorum hatası:", err);
      toast({ title: "AI Hatası", description: "Yorumlar oluşturulamadı. Lütfen tekrar deneyin.", variant: "destructive" });
    } finally {
      setAiYukleniyor(false);
    }
  };

  // ── Anlama yüzdesi hesapla ──
  const hesaplaAnlamaYuzde = () => {
    const alanlar = [
      anlama.cumle_anlama, anlama.bilinmeyen_sozcuk, anlama.baglac_zamir,
      anlama.ana_fikir, anlama.yardimci_fikir, anlama.konu, anlama.baslik_onerme,
      anlama.neden_sonuc, anlama.cikarim, anlama.ipuclari, anlama.yorumlama,
      anlama.gorus_bildirme, anlama.yazar_amaci, anlama.alternatif_fikir, anlama.guncelle_hayat,
      anlama.bilgi, anlama.kavrama, anlama.uygulama, anlama.analiz, anlama.sentez, anlama.degerlendirme,
      ...ekAnlamaOlcutleri.map(o => o.value),
    ];
    const puanMap = { zayif: 0, orta: 1, iyi: 2 };
    const toplam = alanlar.reduce((s, a) => s + (puanMap[a] || 1), 0);
    return Math.round(toplam / (alanlar.length * 2) * 100);
  };

  // ── Düzenlenebilir yorum bileşeni ──
  const YorumAlani = ({ baslik, alan, placeholder }) => (
    <div className="mb-4">
      <label className="text-sm font-semibold text-gray-700 mb-1 block">{baslik}</label>
      <textarea
        value={aiYorumlar[alan]}
        onChange={e => setAiYorumlar({ ...aiYorumlar, [alan]: e.target.value })}
        rows={4}
        placeholder={placeholder || "AI ile oluşturun veya el ile yazın..."}
        className="w-full border border-gray-300 rounded-xl p-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400 resize-none leading-relaxed"
      />
    </div>
  );

  // ── Kaydet ──
  const kaydet = async () => {
    try {
      // Ek ölçütleri anlama objesine ekle
      const anlamaFull = { ...anlama };
      ekAnlamaOlcutleri.forEach(o => { anlamaFull[o.id] = o.value; });

      // Ek prozodik ölçütleri prozodik objesine ekle
      const prozodikFull = { ...prozodik };
      ekProzodikOlcutleri.forEach(o => { prozodikFull[o.id] = o.puan; });

      // AI yorumlarını öğretmen notuna birleştir
      let tamNot = "";
      if (aiOlusturuldu || Object.values(aiYorumlar).some(v => v)) {
        const bolumler = [
          { baslik: "OKUMA HIZI DEĞERLENDİRMESİ", icerik: aiYorumlar.hiz },
          { baslik: "DOĞRU OKUMA ORANI DEĞERLENDİRMESİ", icerik: aiYorumlar.dogruluk },
          { baslik: "OKUDUĞUNU ANLAMA DEĞERLENDİRMESİ", icerik: aiYorumlar.anlama },
          { baslik: "PROZODİK OKUMA DEĞERLENDİRMESİ", icerik: aiYorumlar.prozodik },
          { baslik: "SONUÇ VE GENEL YORUM", icerik: aiYorumlar.sonuc },
          { baslik: "EĞİTSEL VE EV TEMELLİ GELİŞİM ÖNERİLERİ", icerik: aiYorumlar.oneriler },
        ];
        tamNot = bolumler.filter(b => b.icerik).map(b => `${b.baslik}:\n${b.icerik}`).join("\n\n");
        if (ogretmenNotu) tamNot += `\n\nÖĞRETMEN EK NOTU:\n${ogretmenNotu}`;
      } else {
        tamNot = ogretmenNotu;
      }

      // Ek ölçüt bilgilerini de nota ekle
      if (ekAnlamaOlcutleri.length > 0) {
        tamNot += `\n\nEK ANLAMA ÖLÇÜTLERİ: ${ekAnlamaOlcutleri.map(o => `${o.etiket}: ${seviyeLabel[o.value]}`).join(", ")}`;
      }
      if (ekProzodikOlcutleri.length > 0) {
        tamNot += `\nEK PROZODİK ÖLÇÜTLER: ${ekProzodikOlcutleri.map(o => `${o.etiket}: ${o.puan}/4`).join(", ")}`;
      }

      const r = await axios.post(`${API}/diagnostic/rapor`, {
        oturum_id: oturum.id,
        anlama: anlamaFull,
        prozodik: prozodikFull,
        ogretmen_notu: tamNot,
      });

      // AI yorumlarını rapor verisine ekle (DOCX oluşturucu için)
      const raporData = { ...r.data, ai_yorumlar: aiYorumlar, ek_anlama: ekAnlamaOlcutleri, ek_prozodik: ekProzodikOlcutleri };

      toast({ title: "✅ Rapor oluşturuldu!" });
      onRaporTamamla(raporData);
    } catch(e) {
      toast({ title: "Hata", description: e.response?.data?.detail, variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="text-center">
        <h2 className="text-2xl font-bold">Rapor Doldur</h2>
        <p className="text-gray-500">{ogrenci.ad} {ogrenci.soyad} — {ogrenci.sinif}</p>
      </div>

      {/* Özet bilgiler */}
      <div className="grid grid-cols-3 gap-3">
        <Card className="border-0 shadow-sm text-center"><CardContent className="p-4">
          <div className="text-2xl font-bold text-blue-600">{sonuc.wpm}</div>
          <div className="text-xs text-gray-500">kelime/dk</div>
        </CardContent></Card>
        <Card className="border-0 shadow-sm text-center"><CardContent className="p-4">
          <div className="text-2xl font-bold text-green-600">%{sonuc.dogruluk_yuzde}</div>
          <div className="text-xs text-gray-500">doğruluk</div>
        </CardContent></Card>
        <Card className="border-0 shadow-sm text-center"><CardContent className="p-4">
          <div className="text-2xl font-bold text-orange-600">{sonuc.atanan_kur || sonuc.sistem_kur}</div>
          <div className="text-xs text-gray-500">atanan kur</div>
        </CardContent></Card>
      </div>

      {/* ══ 4. Okuduğunu Anlama ══ */}
      <Card className="border-0 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base flex items-center justify-between">
            <span>4. Okuduğunu Anlama Becerileri</span>
            <button onClick={() => setAnlamaEkleAcik(!anlamaEkleAcik)}
              className="text-xs px-3 py-1 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition-all border border-blue-200">
              + Ölçüt Ekle
            </button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Ölçüt ekleme formu */}
          {anlamaEkleAcik && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 space-y-3">
              <div className="text-sm font-semibold text-blue-700">Yeni Anlama Ölçütü Ekle</div>
              <input value={yeniAnlamaAdi} onChange={e => setYeniAnlamaAdi(e.target.value)}
                placeholder="Ölçüt adı (ör: Metafor anlama)"
                className="w-full border border-blue-300 rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400" />
              <select value={yeniAnlamaKat} onChange={e => setYeniAnlamaKat(e.target.value)}
                className="w-full border border-blue-300 rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400">
                {Object.entries(anlamaKategoriler).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
              <div className="flex gap-2">
                <button onClick={anlamaOlcutEkle}
                  className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">Ekle</button>
                <button onClick={() => setAnlamaEkleAcik(false)}
                  className="px-4 py-2 bg-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-300">İptal</button>
              </div>
            </div>
          )}

          {/* 4.1 Sözcük */}
          <div>
            <h4 className="text-sm font-semibold text-gray-600 mb-2 bg-gray-50 p-2 rounded-lg">4.1 Sözcük Düzeyinde Anlama</h4>
            <SeviyeSecici alan="cumle_anlama" etiket="Cümle anlamını kavrama" />
            <SeviyeSecici alan="bilinmeyen_sozcuk" etiket="Bilinmeyen sözcük tahmini" />
            <SeviyeSecici alan="baglac_zamir" etiket="Bağlaç ve zamirleri anlama" />
            {ekAnlamaOlcutleri.filter(o => o.kategori === "sozcuk").map(o => (
              <SeviyeSecici key={o.id} isEk ekId={o.id} etiket={o.etiket} />
            ))}
          </div>

          {/* 4.2 Ana yapı */}
          <div>
            <h4 className="text-sm font-semibold text-gray-600 mb-2 bg-gray-50 p-2 rounded-lg">4.2 Metnin Ana Yapısını Anlama</h4>
            <SeviyeSecici alan="ana_fikir" etiket="Ana fikir belirleme" />
            <SeviyeSecici alan="yardimci_fikir" etiket="Yardımcı fikirleri ifade etme" />
            <SeviyeSecici alan="konu" etiket="Metnin konusunu ifade etme" />
            <SeviyeSecici alan="baslik_onerme" etiket="Başlık önerme" />
            {ekAnlamaOlcutleri.filter(o => o.kategori === "ana_yapi").map(o => (
              <SeviyeSecici key={o.id} isEk ekId={o.id} etiket={o.etiket} />
            ))}
          </div>

          {/* 4.3 Derin anlama */}
          <div>
            <h4 className="text-sm font-semibold text-gray-600 mb-2 bg-gray-50 p-2 rounded-lg">4.3 Metinler Arasılık ve Derin Anlama</h4>
            <SeviyeSecici alan="neden_sonuc" etiket="Neden-sonuç ilişkisini belirleme" />
            <SeviyeSecici alan="cikarim" etiket="Çıkarım yapma" />
            <SeviyeSecici alan="ipuclari" etiket="Metindeki ipuçlarını kullanma" />
            <SeviyeSecici alan="yorumlama" etiket="Yorumlama" />
            {ekAnlamaOlcutleri.filter(o => o.kategori === "derin").map(o => (
              <SeviyeSecici key={o.id} isEk ekId={o.id} etiket={o.etiket} />
            ))}
          </div>

          {/* 4.4 Eleştirel */}
          <div>
            <h4 className="text-sm font-semibold text-gray-600 mb-2 bg-gray-50 p-2 rounded-lg">4.4 Eleştirel ve Yaratıcı Okuma</h4>
            <SeviyeSecici alan="gorus_bildirme" etiket="Metne yönelik görüş bildirme" />
            <SeviyeSecici alan="yazar_amaci" etiket="Yazarın amacını sezme" />
            <SeviyeSecici alan="alternatif_fikir" etiket="Alternatif son / fikir üretme" />
            <SeviyeSecici alan="guncelle_hayat" etiket="Metni günlük hayatla ilişkilendirme" />
            {ekAnlamaOlcutleri.filter(o => o.kategori === "elestirel").map(o => (
              <SeviyeSecici key={o.id} isEk ekId={o.id} etiket={o.etiket} />
            ))}
          </div>

          {/* 4.5 Soru performans */}
          <div>
            <h4 className="text-sm font-semibold text-gray-600 mb-2 bg-gray-50 p-2 rounded-lg">4.5 Soru Performans Analizi</h4>
            <SeviyeSecici alan="bilgi" etiket="Bilgi" />
            <SeviyeSecici alan="kavrama" etiket="Kavrama" />
            <SeviyeSecici alan="uygulama" etiket="Uygulama" />
            <SeviyeSecici alan="analiz" etiket="Analiz" />
            <SeviyeSecici alan="sentez" etiket="Sentez" />
            <SeviyeSecici alan="degerlendirme" etiket="Değerlendirme" />
            {ekAnlamaOlcutleri.filter(o => o.kategori === "soru").map(o => (
              <SeviyeSecici key={o.id} isEk ekId={o.id} etiket={o.etiket} />
            ))}
          </div>

          {/* Anlama yüzdesi */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
            <Label>Genel Anlama Yüzdesi (%)</Label>
            <div className="flex items-center gap-3 mt-2">
              <input type="number" min="0" max="100" value={anlama.genel_yuzde}
                onChange={e => setAnlama({...anlama, genel_yuzde: parseInt(e.target.value)||0})}
                className="w-24 border border-blue-300 rounded-lg p-2 text-center text-lg font-bold focus:outline-none focus:ring-2 focus:ring-blue-400" />
              <span className="text-sm text-gray-500">0 bırakırsanız otomatik hesaplanır: %{hesaplaAnlamaYuzde()}</span>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ══ 5. Prozodik Okuma ══ */}
      <Card className="border-0 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base flex items-center justify-between">
            <span>5. Prozodik Okuma Ölçeği</span>
            <div className="flex items-center gap-3">
              <span className="text-lg font-bold text-orange-600">Toplam: {prozodikToplam}/{20 + ekProzodikOlcutleri.length * 4}</span>
              <button onClick={() => setProzodikEkleAcik(!prozodikEkleAcik)}
                className="text-xs px-3 py-1 bg-orange-50 text-orange-600 rounded-lg hover:bg-orange-100 transition-all border border-orange-200">
                + Ölçüt Ekle
              </button>
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {/* Prozodik ölçüt ekleme */}
          {prozodikEkleAcik && (
            <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 space-y-3 mb-4">
              <div className="text-sm font-semibold text-orange-700">Yeni Prozodik Ölçüt Ekle</div>
              <input value={yeniProzodikAdi} onChange={e => setYeniProzodikAdi(e.target.value)}
                placeholder="Ölçüt adı (ör: Diyalog ifadesi)"
                className="w-full border border-orange-300 rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400" />
              <div className="flex gap-2">
                <button onClick={prozodikOlcutEkle}
                  className="px-4 py-2 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700">Ekle</button>
                <button onClick={() => setProzodikEkleAcik(false)}
                  className="px-4 py-2 bg-gray-200 text-gray-700 text-sm rounded-lg hover:bg-gray-300">İptal</button>
              </div>
            </div>
          )}

          <ProzodikSatir alan="noktalama" etiket="Noktalama ve Duraklama"
            aciklama1="Uymuyor" aciklama2="Kısmen uyuyor" aciklama3="Çoğunlukla" aciklama4="Tam ve bilinçli" />
          <ProzodikSatir alan="vurgu" etiket="Vurgu"
            aciklama1="Tek düze" aciklama2="Yer yer vurgu" aciklama3="Anlama uygun" aciklama4="Etkili ve bilinçli" />
          <ProzodikSatir alan="tonlama" etiket="Tonlama"
            aciklama1="Monoton" aciklama2="Sınırlı" aciklama3="Metne uygun" aciklama4="Doğal ve etkileyici" />
          <ProzodikSatir alan="akicilik" etiket="Akıcılık"
            aciklama1="Sık duraklama" aciklama2="Kısmi akış" aciklama3="Genel olarak akıcı" aciklama4="Kesintisiz akıcı" />
          <ProzodikSatir alan="anlamli_gruplama" etiket="Anlamlı Gruplama"
            aciklama1="Sözcük sözcük" aciklama2="Kısmen gruplama" aciklama3="Çoğunlukla doğru" aciklama4="Tam ve tutarlı" />

          {/* Ek prozodik ölçütler */}
          {ekProzodikOlcutleri.map(o => (
            <ProzodikSatir key={o.id} isEk ekId={o.id} etiket={o.etiket}
              aciklama1={o.aciklamalar[0]} aciklama2={o.aciklamalar[1]}
              aciklama3={o.aciklamalar[2]} aciklama4={o.aciklamalar[3]} />
          ))}
        </CardContent>
      </Card>

      {/* ══ 6. AI Yorumları ══ */}
      <Card className="border-0 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base flex items-center justify-between">
            <span>6. Değerlendirme Yorumları</span>
            <button onClick={aiYorumlariOlustur} disabled={aiYukleniyor}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                aiYukleniyor
                  ? 'bg-gray-200 text-gray-500 cursor-not-allowed'
                  : 'bg-gradient-to-r from-purple-500 to-blue-500 text-white hover:from-purple-600 hover:to-blue-600 shadow-md'
              }`}>
              {aiYukleniyor ? (
                <span className="flex items-center gap-2">
                  <span className="animate-spin">⏳</span> AI Oluşturuyor...
                </span>
              ) : aiOlusturuldu ? "🔄 Yeniden Oluştur" : "🤖 AI ile Oluştur"}
            </button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-1">
          {!aiOlusturuldu && !Object.values(aiYorumlar).some(v => v) && (
            <div className="text-center py-8 text-gray-400">
              <div className="text-4xl mb-3">🤖</div>
              <p className="text-sm">Önce yukarıdaki ölçütleri doldurun, sonra<br/><strong>"AI ile Oluştur"</strong> butonuna tıklayın</p>
              <p className="text-xs mt-2 text-gray-400">AI, sayısal verilere göre her bölüm için profesyonel yorum yazacak.</p>
              <p className="text-xs text-gray-400">Oluşturulan yorumları istediğiniz gibi düzenleyebilirsiniz.</p>
            </div>
          )}
          {(aiOlusturuldu || Object.values(aiYorumlar).some(v => v)) && (
            <>
              <YorumAlani baslik="📊 Okuma Hızı Değerlendirmesi" alan="hiz" placeholder="Okuma hızına ilişkin değerlendirme..." />
              <YorumAlani baslik="✅ Doğru Okuma Oranı Değerlendirmesi" alan="dogruluk" placeholder="Doğruluk ve hata analizi..." />
              <YorumAlani baslik="📖 Okuduğunu Anlama Değerlendirmesi" alan="anlama" placeholder="Anlama becerileri değerlendirmesi..." />
              <YorumAlani baslik="🎵 Prozodik Okuma Değerlendirmesi" alan="prozodik" placeholder="Prozodik okuma değerlendirmesi..." />
              <YorumAlani baslik="📝 Sonuç ve Genel Yorum" alan="sonuc" placeholder="Genel sonuç ve yorum..." />
              <YorumAlani baslik="🎯 Eğitsel ve Ev Temelli Gelişim Önerileri" alan="oneriler" placeholder="Gelişim önerileri..." />
            </>
          )}
        </CardContent>
      </Card>

      {/* ══ 7. Öğretmen Ek Notu ══ */}
      <Card className="border-0 shadow-sm">
        <CardHeader><CardTitle className="text-base">7. Öğretmen Ek Notu</CardTitle></CardHeader>
        <CardContent>
          <textarea value={ogretmenNotu} onChange={e => setOgretmenNotu(e.target.value)} rows={4}
            placeholder="Öğrenciye ilişkin ek değerlendirme ve notlarınızı yazın..."
            className="w-full border border-gray-300 rounded-xl p-4 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 resize-none leading-relaxed" />
        </CardContent>
      </Card>

      <Button onClick={kaydet} className="w-full py-4 bg-gradient-to-r from-orange-500 to-red-500 text-white font-bold text-lg">
        📄 Raporu Oluştur
      </Button>
    </div>
  );
}

// ── RAPOR GÖRÜNTÜLE ──
function RaporGoruntule({ rapor, ogrenci, onGeri }) {
  const hizLabel = { dusuk: "Düşük", orta: "Orta", yeterli: "Yeterli", ileri: "İleri" };
  const seviyeRenk = { zayif: "text-red-600", orta: "text-yellow-600", iyi: "text-green-600" };
  const seviyeLabel = { zayif: "Zayıf", orta: "Orta", iyi: "İyi" };
  const prozodikSeviye = (t) => t >= 18 ? "Çok İyi" : t >= 14 ? "İyi" : t >= 10 ? "Orta" : "Geliştirilmeli";
  const formatTarih = (t) => new Date(t).toLocaleDateString("tr-TR");
  const formatSure = (s) => `${Math.floor(s/60)}:${Math.round(s%60).toString().padStart(2,'0')}`;

  const AnlamaTablosu = ({ baslik, satirlar }) => (
    <div className="mb-4">
      <div className="bg-gray-100 px-3 py-2 rounded-t-lg font-semibold text-sm text-gray-700">{baslik}</div>
      <table className="w-full border border-gray-200 rounded-b-lg overflow-hidden text-sm">
        <thead><tr className="bg-gray-50">
          <th className="text-left p-2 border-b border-gray-200 font-medium">Ölçüt</th>
          <th className="p-2 border-b border-gray-200 w-20 text-center font-medium">Zayıf</th>
          <th className="p-2 border-b border-gray-200 w-20 text-center font-medium">Orta</th>
          <th className="p-2 border-b border-gray-200 w-20 text-center font-medium">İyi</th>
        </tr></thead>
        <tbody>
          {satirlar.map(([etiket, alan]) => {
            const deger = rapor.anlama?.[alan] || "orta";
            return (
              <tr key={alan} className="border-b border-gray-100 last:border-0">
                <td className="p-2 text-gray-700">{etiket}</td>
                {["zayif","orta","iyi"].map(s => (
                  <td key={s} className="p-2 text-center text-orange-500 font-bold">{deger === s ? "+" : ""}</td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={onGeri}>← Geri</Button>
        <h2 className="text-xl font-bold">Okuma Becerileri Ölçüm Raporu</h2>
      </div>

      {/* 1. Öğrenci Bilgileri */}
      <Card className="border-0 shadow-sm">
        <CardHeader><CardTitle className="text-base bg-gray-800 text-white p-3 rounded-lg -m-1">1. ÖĞRENCİ BİLGİLERİ</CardTitle></CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <tbody>
              <tr className="border-b"><td className="p-3 font-semibold w-48 bg-gray-50">Adı Soyadı:</td><td className="p-3">{rapor.ogrenci_ad}</td></tr>
              <tr className="border-b"><td className="p-3 font-semibold bg-gray-50">Sınıfı:</td><td className="p-3">{rapor.ogrenci_sinif}</td></tr>
              <tr className="border-b"><td className="p-3 font-semibold bg-gray-50">Değerlendirme Tarihi:</td><td className="p-3">{formatTarih(rapor.olusturma_tarihi)}</td></tr>
              <tr><td className="p-3 font-semibold bg-gray-50">Değerlendirmeyi Yapan:</td><td className="p-3">{rapor.ogretmen_ad}</td></tr>
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* 2. Metin */}
      <Card className="border-0 shadow-sm">
        <CardHeader><CardTitle className="text-base bg-gray-800 text-white p-3 rounded-lg -m-1">2. METİN</CardTitle></CardHeader>
        <CardContent className="p-0">
          <table className="w-full text-sm">
            <tbody>
              <tr className="border-b"><td className="p-3 font-semibold w-48 bg-gray-50">Metnin Adı:</td><td className="p-3 uppercase">{rapor.metin_adi}</td></tr>
              <tr className="border-b"><td className="p-3 font-semibold bg-gray-50">Metnin Türü:</td><td className="p-3 uppercase">{rapor.metin_turu}</td></tr>
              <tr className="border-b"><td className="p-3 font-semibold bg-gray-50">Toplam Kelime Sayısı:</td><td className="p-3">{rapor.kelime_sayisi}</td></tr>
              <tr className="border-b"><td className="p-3 font-semibold bg-gray-50">Doğru Okunan Kelime:</td><td className="p-3">{Math.round(rapor.kelime_sayisi * rapor.dogruluk_yuzde / 100)}</td></tr>
              <tr className="border-b"><td className="p-3 font-semibold bg-gray-50">Yanlış Okunan Kelime:</td><td className="p-3">{rapor.kelime_sayisi - Math.round(rapor.kelime_sayisi * rapor.dogruluk_yuzde / 100)}</td></tr>
              <tr><td className="p-3 font-semibold bg-gray-50">Tamamlama Süresi:</td><td className="p-3">{formatSure(rapor.sure_saniye)} ({rapor.sure_saniye} sn)</td></tr>
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* 3. Okuma Hızı */}
      <Card className="border-0 shadow-sm">
        <CardHeader><CardTitle className="text-base bg-gray-800 text-white p-3 rounded-lg -m-1">3. OKUMA HIZI</CardTitle></CardHeader>
        <CardContent className="pt-4">
          <div className="flex items-center gap-4 mb-4">
            <div className="text-4xl font-bold text-blue-600">{rapor.wpm}</div>
            <div>
              <div className="text-sm text-gray-500">kelime/dakika</div>
              <div className={`font-semibold ${rapor.hiz_deger === "ileri" ? "text-green-600" : rapor.hiz_deger === "yeterli" ? "text-blue-600" : rapor.hiz_deger === "orta" ? "text-yellow-600" : "text-red-600"}`}>
                {hizLabel[rapor.hiz_deger]} Düzey
              </div>
            </div>
          </div>
          <p className="text-sm text-gray-700 leading-relaxed bg-blue-50 p-3 rounded-xl">
            Öğrencinin okuma hızı dakikada <strong>{rapor.wpm} kelime</strong>dir. Bu okuma hızı, öğrencinin bulunduğu sınıf düzeyi normlarına göre <strong>{hizLabel[rapor.hiz_deger]?.toLowerCase()} düzeydedir</strong>.
          </p>
        </CardContent>
      </Card>

      {/* 4. Okuduğunu Anlama */}
      <Card className="border-0 shadow-sm">
        <CardHeader>
          <CardTitle className="text-base bg-gray-800 text-white p-3 rounded-lg -m-1">
            4. OKUDUĞUNU ANLAMA BECERİLERİ — %{rapor.anlama_yuzde}
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4 space-y-4">
          <AnlamaTablosu baslik="4.1 Sözcük Düzeyinde Anlama" satirlar={[
            ["Cümle anlamını kavrama","cumle_anlama"],
            ["Bilinmeyen sözcük tahmini","bilinmeyen_sozcuk"],
            ["Bağlaç ve zamirleri anlama","baglac_zamir"],
          ]} />
          <AnlamaTablosu baslik="4.2 Metnin Ana Yapısını Anlama" satirlar={[
            ["Ana fikir belirleme","ana_fikir"],
            ["Yardımcı fikirleri ifade etme","yardimci_fikir"],
            ["Metnin konusunu ifade etme","konu"],
            ["Başlık önerme","baslik_onerme"],
          ]} />
          <AnlamaTablosu baslik="4.3 Metinler Arasılık ve Derin Anlama" satirlar={[
            ["Neden-sonuç ilişkisini belirleme","neden_sonuc"],
            ["Çıkarım yapma","cikarim"],
            ["Metindeki ipuçlarını kullanma","ipuclari"],
            ["Yorumlama","yorumlama"],
          ]} />
          <AnlamaTablosu baslik="4.4 Eleştirel ve Yaratıcı Okuma" satirlar={[
            ["Metne yönelik görüş bildirme","gorus_bildirme"],
            ["Yazarın amacını sezme","yazar_amaci"],
            ["Alternatif son / fikir üretme","alternatif_fikir"],
            ["Metni günlük hayatla ilişkilendirme","guncelle_hayat"],
          ]} />
          <AnlamaTablosu baslik="4.5 Soru Performans Analizi" satirlar={[
            ["Bilgi","bilgi"],["Kavrama","kavrama"],["Uygulama","uygulama"],
            ["Analiz","analiz"],["Sentez","sentez"],["Değerlendirme","degerlendirme"],
          ]} />
        </CardContent>
      </Card>

      {/* 5. Prozodik Okuma */}
      <Card className="border-0 shadow-sm">
        <CardHeader><CardTitle className="text-base bg-gray-800 text-white p-3 rounded-lg -m-1">5. PROZODİK OKUMA ÖLÇEĞİ</CardTitle></CardHeader>
        <CardContent className="pt-4">
          <table className="w-full text-sm border border-gray-200 rounded-xl overflow-hidden mb-4">
            <thead><tr className="bg-gray-100">
              <th className="text-left p-3 font-semibold">Ölçüt</th>
              <th className="text-center p-3 font-semibold w-24">1 puan</th>
              <th className="text-center p-3 font-semibold w-24">2 puan</th>
              <th className="text-center p-3 font-semibold w-24">3 puan</th>
              <th className="text-center p-3 font-semibold w-24">4 puan</th>
              <th className="text-center p-3 font-semibold w-24">Puan</th>
            </tr></thead>
            <tbody>
              {[
                ["Noktalama ve Duraklama","noktalama",["Uymuyor","Kısmen","Çoğunlukla","Tam ve bilinçli"]],
                ["Vurgu","vurgu",["Tek düze","Yer yer","Anlama uygun","Etkili ve bilinçli"]],
                ["Tonlama","tonlama",["Monoton","Sınırlı","Metne uygun","Doğal ve etkileyici"]],
                ["Akıcılık","akicilik",["Sık duraklama","Kısmi akış","Genel akıcı","Kesintisiz"]],
                ["Anlamlı Gruplama","anlamli_gruplama",["Sözcük sözcük","Kısmen","Çoğunlukla","Tam ve tutarlı"]],
              ].map(([etiket, alan, aciklamalar]) => (
                <tr key={alan} className="border-t border-gray-100">
                  <td className="p-3 font-medium">{etiket}</td>
                  {aciklamalar.map((a, i) => (
                    <td key={i} className={`p-2 text-center text-xs ${rapor.prozodik?.[alan] === i+1 ? 'bg-orange-100 font-bold text-orange-700' : 'text-gray-500'}`}>{a}</td>
                  ))}
                  <td className="p-3 text-center font-bold text-orange-600">{rapor.prozodik?.[alan]}</td>
                </tr>
              ))}
              <tr className="bg-gray-50 border-t-2 border-gray-300">
                <td colSpan="5" className="p-3 font-bold text-right">Toplam</td>
                <td className="p-3 text-center font-bold text-xl text-orange-600">{rapor.prozodik_toplam}</td>
              </tr>
            </tbody>
          </table>
          <div className="bg-orange-50 p-3 rounded-xl text-sm text-gray-700">
            Prozodik okuma performansı: <strong>{prozodikSeviye(rapor.prozodik_toplam)}</strong> (Toplam {rapor.prozodik_toplam}/20)
          </div>
        </CardContent>
      </Card>

      {/* 6. Sonuç */}
      {rapor.ogretmen_notu && (
        <Card className="border-0 shadow-sm">
          <CardHeader><CardTitle className="text-base bg-gray-800 text-white p-3 rounded-lg -m-1">6. SONUÇ VE GENEL YORUM</CardTitle></CardHeader>
          <CardContent className="pt-4">
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{rapor.ogretmen_notu}</p>
          </CardContent>
        </Card>
      )}

      <div className="flex gap-3 pb-8">
        <Button onClick={async () => {
          try {
            const r = await axios.get(`${API}/diagnostic/rapor/${rapor.id}/pdf`, { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
            const a = document.createElement('a'); a.href = url;
            a.download = `Rapor_${rapor.ogrenci_ad?.replace(/\s/g,'_')}_${rapor.olusturma_tarihi?.slice(0,10)}.pdf`;
            document.body.appendChild(a); a.click(); a.remove(); window.URL.revokeObjectURL(url);
          } catch(e) { console.error(e); }
        }} className="flex-1 bg-red-600 hover:bg-red-700 text-white">📄 PDF İndir</Button>
        <Button onClick={() => window.print()} variant="outline" className="flex-1">🖨️ Yazdır</Button>
        <Button onClick={onGeri} variant="outline" className="flex-1">← Geri</Button>
      </div>
    </div>
  );
}


// ── ANA GİRİŞ ANALİZİ MODÜLÜ ──
// ═══════════════════════════════════════════════════════════════
// EGZERSİZLER MODÜLÜ — Göz Egzersizleri & Okuma Egzersizleri
// ═══════════════════════════════════════════════════════════════
function EgzersizlerModul({ user, egzersizPuanlari = {}, onTamamla }) {
  const [aktifEgzersiz, setAktifEgzersiz] = useState(null);
  const [egzersizAyar, setEgzersizAyar] = useState({ hiz: 2, boyut: 40, sure: 30, kelimeHiz: 300 });
  const canvasRef = React.useRef(null);
  const animRef = React.useRef(null);
  const [calisiyorMu, setCalisiyorMu] = useState(false);
  const [kalanSure, setKalanSure] = useState(0);
  const [wpmKelimeler, setWpmKelimeler] = useState([]);
  const [wpmIndex, setWpmIndex] = useState(0);
  // Interactive exercise states
  const [schulteGrid, setSchulteGrid] = useState([]);
  const [schulteNext, setSchulteNext] = useState(1);
  const [schulteSize, setSchulteSize] = useState(5);
  const [interSkor, setInterSkor] = useState(0);
  const [interSoru, setInterSoru] = useState(null);
  const [interCevap, setInterCevap] = useState('');
  const [interFeedback, setInterFeedback] = useState(null);
  const [kelimeAvcisiMetin, setKelimeAvcisiMetin] = useState([]);
  const [kelimeAvcisiHedef, setKelimeAvcisiHedef] = useState('');
  const [kelimeAvcisiBulunan, setKelimeAvcisiBulunan] = useState(new Set());
  const [renkSoru, setRenkSoru] = useState(null);

  const egzersizler = [
    { id: 'goz-takip', baslik: 'Göz Takip Egzersizi', icon: '👁️', aciklama: 'Hareket eden topu gözlerinizle takip edin. Göz kaslarını güçlendirir.', renk: 'from-blue-500 to-cyan-500', kat: 'goz' },
    { id: 'goz-sekiz', baslik: 'Sonsuzluk (∞) Egzersizi', icon: '♾️', aciklama: 'Göz sonsuzluk şeklinde hareket eder. Odaklanma ve koordinasyonu geliştirir.', renk: 'from-purple-500 to-pink-500', kat: 'goz' },
    { id: 'goz-zigzag', baslik: 'Zigzag Okuma', icon: '⚡', aciklama: 'Göz zigzag şeklinde hareket eder. Satır takip hızını artırır.', renk: 'from-orange-500 to-red-500', kat: 'goz' },
    { id: 'goz-genisletme', baslik: 'Görüş Alanı Genişletme', icon: '🔭', aciklama: 'Merkeze odaklanırken çevresel görüşü genişletin.', renk: 'from-green-500 to-emerald-500', kat: 'goz' },
    { id: 'odaklanma', baslik: 'Odaklanma Noktası', icon: '🎯', aciklama: 'Merkez noktaya odaklanın, çevredeki harfleri okumaya çalışın.', renk: 'from-teal-500 to-cyan-500', kat: 'goz' },
    { id: 'periferik', baslik: 'Periferik Görüş', icon: '🌀', aciklama: 'Merkeze bakarken kenar harfleri okuyun. Çevresel görüşü güçlendirir.', renk: 'from-rose-500 to-pink-500', kat: 'goz' },
    { id: 'schulte', baslik: 'Schulte Tablosu', icon: '🔢', aciklama: 'Sayıları sırayla bulun. Göz tarama hızını ve dikkat süresini artırır.', renk: 'from-amber-500 to-orange-500', kat: 'goz' },
    { id: 'goz-yoga', baslik: 'Göz Yoga (Uzak-Yakın)', icon: '🧘', aciklama: 'Uzak ve yakın noktalara odaklanın. Göz esnekliğini geliştirir.', renk: 'from-lime-500 to-green-500', kat: 'goz' },
    { id: 'renk-eslestir', baslik: 'Hızlı Renk Eşleştirme', icon: '🎨', aciklama: 'Renkleri hızla eşleştirin. Algı hızını ve dikkat süresini artırır.', renk: 'from-fuchsia-500 to-purple-500', kat: 'goz' },
    { id: 'hizli-kelime', baslik: 'Hızlı Kelime Okuma (RSVP)', icon: '📖', aciklama: 'Kelimeler tek tek hızla gösterilir. Okuma hızını artırır.', renk: 'from-indigo-500 to-blue-500', kat: 'okuma' },
    { id: 'kelime-avcisi', baslik: 'Kelime Avcısı', icon: '🔍', aciklama: 'Metinde hedef kelimeyi bulun. Tarama hızını ve dikkatinizi geliştirir.', renk: 'from-sky-500 to-blue-500', kat: 'okuma' },
    { id: 'ters-kelime', baslik: 'Ters Kelime Okuma', icon: '🔄', aciklama: 'Kelimeleri tersten okuyun. Beyin jimnastiği ve harf farkındalığı.', renk: 'from-violet-500 to-indigo-500', kat: 'okuma' },
    { id: 'eksik-harf', baslik: 'Eksik Harf Tamamlama', icon: '✏️', aciklama: 'Eksik harfleri tamamlayın. Kelime tanıma ve tahmin becerisini geliştirir.', renk: 'from-cyan-500 to-teal-500', kat: 'okuma' },
    { id: 'karisik-cumle', baslik: 'Karışık Cümle Düzenleme', icon: '🧩', aciklama: 'Karışık kelimeleri doğru sıraya dizin. Anlama becerisini güçlendirir.', renk: 'from-red-500 to-rose-500', kat: 'okuma' },
  ];

  const durdur = () => {
    setCalisiyorMu(false);
    if (animRef.current) { cancelAnimationFrame(animRef.current); animRef.current = null; }
  };

  const turkceKelimeler = 'okuma kitap harf sözcük metin sayfa satır anlam öğrenci öğretmen kalem defter sınıf tahta pencere kapı masa sandalye bilgi düşünce hikaye masal roman şiir yazar çocuk anne baba kardeş arkadaş oyun park bahçe çiçek ağaç güneş yıldız ay bulut rüzgar yağmur deniz göl nehir dağ orman kuş kedi köpek balık araba tren uçak gemi yol sokak şehir köy'.split(' ');
  const cumleHavuzu = [
    {d:'Güneş doğarken kuşlar şarkı söylemeye başladı',k:['başladı','söylemeye','şarkı','kuşlar','doğarken','Güneş']},
    {d:'Küçük kedi bahçede kelebekleri kovalıyordu',k:['kovalıyordu','kelebekleri','bahçede','kedi','Küçük']},
    {d:'Çocuklar parkta neşeyle oynuyorlardı',k:['oynuyorlardı','neşeyle','parkta','Çocuklar']},
    {d:'Öğretmen tahtaya güzel bir resim çizdi',k:['çizdi','resim','bir','güzel','tahtaya','Öğretmen']},
    {d:'Yağmur yağınca çocuklar eve koştu',k:['koştu','eve','çocuklar','yağınca','Yağmur']},
    {d:'Annem bize lezzetli bir pasta yaptı',k:['yaptı','pasta','bir','lezzetli','bize','Annem']},
    {d:'Kütüphanede sessizce kitap okuyan çocuklar vardı',k:['vardı','çocuklar','okuyan','kitap','sessizce','Kütüphanede']},
    {d:'Denizde yüzen balıklar çok renkli görünüyordu',k:['görünüyordu','renkli','çok','balıklar','yüzen','Denizde']},
  ];

  const yeniInterSoru = (tip) => {
    if (tip === 'schulte') {
      const n = schulteSize;
      const nums = Array.from({length: n*n}, (_,i) => i+1);
      for (let i = nums.length-1; i > 0; i--) { const j = Math.floor(Math.random()*(i+1)); [nums[i],nums[j]] = [nums[j],nums[i]]; }
      setSchulteGrid(nums); setSchulteNext(1); setInterSkor(0);
    } else if (tip === 'renk-eslestir') {
      const renkler = [{ad:'KIRMIZI',hex:'#ef4444'},{ad:'MAVİ',hex:'#3b82f6'},{ad:'YEŞİL',hex:'#22c55e'},{ad:'SARI',hex:'#eab308'},{ad:'TURUNCU',hex:'#f97316'},{ad:'MOR',hex:'#a855f7'}];
      const r1 = renkler[Math.floor(Math.random()*renkler.length)];
      const r2 = renkler[Math.floor(Math.random()*renkler.length)];
      setRenkSoru({yazi: r1.ad, renk: r2.hex, dogruRenk: r2.ad, secenekler: renkler.sort(() => Math.random()-0.5).slice(0,4)});
      setInterSkor(0);
    } else if (tip === 'kelime-avcisi') {
      const metin = []; for (let i = 0; i < 60; i++) metin.push(turkceKelimeler[Math.floor(Math.random()*turkceKelimeler.length)]);
      const hedef = metin[Math.floor(Math.random()*metin.length)];
      setKelimeAvcisiMetin(metin); setKelimeAvcisiHedef(hedef); setKelimeAvcisiBulunan(new Set()); setInterSkor(0);
    } else if (tip === 'ters-kelime') {
      const k = turkceKelimeler[Math.floor(Math.random()*turkceKelimeler.length)];
      setInterSoru({kelime: k, ters: k.split('').reverse().join('')}); setInterCevap(''); setInterFeedback(null); setInterSkor(0);
    } else if (tip === 'eksik-harf') {
      const k = turkceKelimeler[Math.floor(Math.random()*turkceKelimeler.length)];
      const idx = Math.floor(Math.random()*k.length);
      setInterSoru({kelime: k, eksikIdx: idx, gosterim: k.split('').map((h,i) => i===idx ? '_' : h).join('')}); setInterCevap(''); setInterFeedback(null); setInterSkor(0);
    } else if (tip === 'karisik-cumle') {
      const c = cumleHavuzu[Math.floor(Math.random()*cumleHavuzu.length)];
      setInterSoru({dogru: c.d, karisik: [...c.k].sort(() => Math.random()-0.5), secilen: []}); setInterFeedback(null); setInterSkor(0);
    }
  };

  const baslat = (id) => {
    setAktifEgzersiz(id);
    setCalisiyorMu(true);
    setKalanSure(egzersizAyar.sure);
    setInterSkor(0);
    setInterFeedback(null);
    if (['schulte','renk-eslestir','kelime-avcisi','ters-kelime','eksik-harf','karisik-cumle'].includes(id)) {
      yeniInterSoru(id);
    }
  };

  // Geri sayım
  React.useEffect(() => {
    if (!calisiyorMu || kalanSure <= 0) { if (kalanSure <= 0 && calisiyorMu) { durdur(); if (onTamamla && aktifEgzersiz) onTamamla(aktifEgzersiz); } return; }
    const t = setTimeout(() => setKalanSure(k => k - 1), 1000);
    return () => clearTimeout(t);
  }, [calisiyorMu, kalanSure]);

  // Canvas animasyonları
  React.useEffect(() => {
    if (!calisiyorMu || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const W = canvas.width = canvas.offsetWidth;
    const H = canvas.height = canvas.offsetHeight;
    let t = 0;
    const speed = egzersizAyar.hiz;
    const sz = egzersizAyar.boyut;

    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      t += 0.02 * speed;
      let x, y;

      if (aktifEgzersiz === 'goz-takip') {
        // Düz yatay hareket
        x = W/2 + Math.cos(t) * (W/2 - sz);
        y = H/2 + Math.sin(t * 0.7) * (H/3);
        ctx.beginPath(); ctx.arc(x, y, sz/2, 0, Math.PI*2);
        const grad = ctx.createRadialGradient(x, y, 0, x, y, sz/2);
        grad.addColorStop(0, '#60a5fa'); grad.addColorStop(1, '#2563eb');
        ctx.fillStyle = grad; ctx.fill();
        ctx.strokeStyle = '#1d4ed8'; ctx.lineWidth = 2; ctx.stroke();
        // Göz parıltısı
        ctx.beginPath(); ctx.arc(x - sz/6, y - sz/6, sz/8, 0, Math.PI*2);
        ctx.fillStyle = 'rgba(255,255,255,0.7)'; ctx.fill();
      }
      else if (aktifEgzersiz === 'goz-sekiz') {
        // Sonsuzluk şekli (lemniscate)
        const scale = Math.min(W, H) * 0.35;
        x = W/2 + scale * Math.cos(t) / (1 + Math.sin(t)*Math.sin(t));
        y = H/2 + scale * Math.sin(t) * Math.cos(t) / (1 + Math.sin(t)*Math.sin(t));
        // İz çiz
        ctx.beginPath(); ctx.strokeStyle = 'rgba(168,85,247,0.15)'; ctx.lineWidth = 3;
        for (let i = 0; i < Math.PI * 2; i += 0.05) {
          const ix = W/2 + scale * Math.cos(i) / (1 + Math.sin(i)*Math.sin(i));
          const iy = H/2 + scale * Math.sin(i) * Math.cos(i) / (1 + Math.sin(i)*Math.sin(i));
          i === 0 ? ctx.moveTo(ix, iy) : ctx.lineTo(ix, iy);
        }
        ctx.stroke();
        ctx.beginPath(); ctx.arc(x, y, sz/2, 0, Math.PI*2);
        const grad = ctx.createRadialGradient(x, y, 0, x, y, sz/2);
        grad.addColorStop(0, '#c084fc'); grad.addColorStop(1, '#9333ea');
        ctx.fillStyle = grad; ctx.fill();
      }
      else if (aktifEgzersiz === 'goz-zigzag') {
        const rows = 5;
        const progress = (t % (rows * Math.PI)) / (rows * Math.PI);
        const row = Math.floor(progress * rows);
        const rowProgress = (progress * rows) % 1;
        x = row % 2 === 0 ? rowProgress * W : (1 - rowProgress) * W;
        y = (row + 0.5) / rows * H;
        // Zigzag izi
        ctx.beginPath(); ctx.strokeStyle = 'rgba(249,115,22,0.15)'; ctx.lineWidth = 2;
        for (let r = 0; r < rows; r++) {
          const lx = r % 2 === 0 ? 20 : W - 20;
          const rx = r % 2 === 0 ? W - 20 : 20;
          const ry = (r + 0.5) / rows * H;
          ctx.moveTo(lx, ry); ctx.lineTo(rx, ry);
          if (r < rows - 1) { const ny = (r + 1.5) / rows * H; ctx.lineTo(rx, ny); }
        }
        ctx.stroke();
        ctx.beginPath(); ctx.arc(x, y, sz/2, 0, Math.PI*2);
        ctx.fillStyle = '#f97316'; ctx.fill();
      }
      else if (aktifEgzersiz === 'goz-genisletme') {
        // Merkez nokta + genişleyen çember
        ctx.beginPath(); ctx.arc(W/2, H/2, 8, 0, Math.PI*2);
        ctx.fillStyle = '#ef4444'; ctx.fill();
        const radius = 30 + Math.abs(Math.sin(t * 0.5)) * (Math.min(W, H)/2 - 50);
        ctx.beginPath(); ctx.arc(W/2, H/2, radius, 0, Math.PI*2);
        ctx.strokeStyle = `rgba(16,185,129,${0.8 - radius / (Math.min(W,H)/2) * 0.6})`; ctx.lineWidth = 3; ctx.stroke();
        // Çevresel harfler
        const harfler = 'ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ';
        const harfSayi = 12;
        ctx.font = '18px sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        for (let i = 0; i < harfSayi; i++) {
          const angle = (i / harfSayi) * Math.PI * 2 + t * 0.3;
          const hx = W/2 + Math.cos(angle) * radius;
          const hy = H/2 + Math.sin(angle) * radius;
          ctx.fillStyle = `rgba(16,185,129,${0.9 - radius / (Math.min(W,H)/2) * 0.5})`;
          ctx.fillText(harfler[Math.floor(Math.random() * harfler.length)], hx, hy);
        }
        ctx.font = '12px sans-serif'; ctx.fillStyle = '#666';
        ctx.fillText('Kırmızı noktaya odaklanın', W/2, H - 20);
      }
      else if (aktifEgzersiz === 'odaklanma') {
        ctx.beginPath(); ctx.arc(W/2, H/2, 10, 0, Math.PI*2);
        ctx.fillStyle = '#ef4444'; ctx.fill();
        for (let r = 1; r <= 4; r++) {
          ctx.beginPath(); ctx.arc(W/2, H/2, r * 50, 0, Math.PI*2);
          ctx.strokeStyle = `rgba(99,102,241,${0.3 - r * 0.05})`; ctx.lineWidth = 1; ctx.stroke();
        }
        const harfler2 = 'ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ0123456789';
        ctx.font = '16px monospace'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const harfFrame = Math.floor(t * 2);
        for (let i = 0; i < 8; i++) {
          const angle = (i / 8) * Math.PI * 2;
          const dist = 80 + Math.sin(t + i) * 30;
          const hx = W/2 + Math.cos(angle) * dist;
          const hy = H/2 + Math.sin(angle) * dist;
          ctx.fillStyle = '#4f46e5';
          ctx.fillText(harfler2[(harfFrame + i * 3) % harfler2.length], hx, hy);
        }
      }
      else if (aktifEgzersiz === 'periferik') {
        // Merkez kelime + çevrede genişleyen harfler
        ctx.fillStyle = '#ef4444'; ctx.beginPath(); ctx.arc(W/2, H/2, 6, 0, Math.PI*2); ctx.fill();
        const kelimeler = ['OKUMA','KİTAP','HARF','SÖZCÜK','METİN','SAYFA','SATIR','ANLAM'];
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        const ring1 = 80, ring2 = 150, ring3 = 220;
        [ring1, ring2, ring3].forEach((ring, ri) => {
          ctx.beginPath(); ctx.arc(W/2, H/2, ring, 0, Math.PI*2);
          ctx.strokeStyle = `rgba(244,63,94,${0.15 - ri*0.04})`; ctx.lineWidth = 1; ctx.stroke();
          const count = 4 + ri * 2;
          const fontSize = 18 - ri * 3;
          ctx.font = `bold ${fontSize}px sans-serif`;
          for (let i = 0; i < count; i++) {
            const a = (i / count) * Math.PI * 2 + t * (0.2 - ri * 0.05);
            const px = W/2 + Math.cos(a) * ring;
            const py = H/2 + Math.sin(a) * ring;
            ctx.fillStyle = `rgba(244,63,94,${0.9 - ri * 0.25})`;
            ctx.fillText(kelimeler[(Math.floor(t * 2) + i + ri * 3) % kelimeler.length], px, py);
          }
        });
        ctx.font = '11px sans-serif'; ctx.fillStyle = '#999';
        ctx.fillText('Kırmızı noktaya odaklanıp çevredeki kelimeleri okuyun', W/2, H - 15);
      }
      else if (aktifEgzersiz === 'goz-yoga') {
        // Uzak-yakın odaklanma: büyüyüp küçülen daire
        const phase = Math.sin(t * 0.4);
        const minR = 15, maxR = Math.min(W, H) * 0.35;
        const r = minR + (phase * 0.5 + 0.5) * (maxR - minR);
        const isYakin = phase > 0;
        // Arka plan gradient
        const bgGrad = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, maxR + 50);
        bgGrad.addColorStop(0, isYakin ? 'rgba(132,204,22,0.1)' : 'rgba(132,204,22,0.02)');
        bgGrad.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = bgGrad; ctx.fillRect(0, 0, W, H);
        // Ana daire
        ctx.beginPath(); ctx.arc(W/2, H/2, r, 0, Math.PI*2);
        const cGrad = ctx.createRadialGradient(W/2, H/2, 0, W/2, H/2, r);
        cGrad.addColorStop(0, '#84cc16'); cGrad.addColorStop(1, '#65a30d');
        ctx.fillStyle = cGrad; ctx.globalAlpha = 0.8; ctx.fill(); ctx.globalAlpha = 1;
        // İç nokta
        ctx.beginPath(); ctx.arc(W/2, H/2, 5, 0, Math.PI*2);
        ctx.fillStyle = '#fff'; ctx.fill();
        // Yazı
        ctx.font = 'bold 16px sans-serif'; ctx.textAlign = 'center'; ctx.fillStyle = '#fff';
        ctx.fillText(isYakin ? 'YAKIN' : 'UZAK', W/2, H/2 + r + 30);
        ctx.font = '12px sans-serif'; ctx.fillStyle = '#666';
        ctx.fillText('Yeşil daireye odaklanın — büyürken yakına, küçülürken uzağa bakın', W/2, H - 15);
      }

      animRef.current = requestAnimationFrame(draw);
    };
    draw();
    return () => { if (animRef.current) cancelAnimationFrame(animRef.current); };
  }, [calisiyorMu, aktifEgzersiz, egzersizAyar]);

  // RSVP kelime gösterici
  React.useEffect(() => {
    if (!calisiyorMu || aktifEgzersiz !== 'hizli-kelime') return;
    const ornek = "Bir varmış bir yokmuş evvel zaman içinde kalbur saman içinde uzak diyarların birinde yaşlı bir bilge yaşarmış Bu bilge her gün sabahın erken saatlerinde kalkıp ormana yürüyüşe çıkarmış Ormanın derinliklerinde akan bir dere varmış Derenin kenarında oturup düşünür kuşların şarkılarını dinlermiş Bir gün küçük bir çocuk bilgenin yanına gelmiş ve sormuş Bilge dede mutluluğun sırrı nedir Bilge gülümsemiş ve demiş ki Mutluluk aradığın yerde değil olduğun yerdedir".split(' ');
    setWpmKelimeler(ornek);
    setWpmIndex(0);
    const ms = 60000 / egzersizAyar.kelimeHiz;
    const interval = setInterval(() => {
      setWpmIndex(prev => { if (prev >= ornek.length - 1) return 0; return prev + 1; });
    }, ms);
    return () => clearInterval(interval);
  }, [calisiyorMu, aktifEgzersiz, egzersizAyar.kelimeHiz]);

  return (
    <div>
      {!aktifEgzersiz ? (
        <div>
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold flex items-center gap-2"><Eye className="h-6 w-6" /> Egzersiz Merkezi</h2>
          </div>
          <h3 className="text-sm font-bold text-gray-500 mb-3 uppercase tracking-wide">👁️ Göz Egzersizleri</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
            {egzersizler.filter(e => e.kat === 'goz').map(eg => (
              <div key={eg.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden hover:shadow-md transition-shadow cursor-pointer" onClick={() => setAktifEgzersiz(eg.id)}>
                <div className={`bg-gradient-to-r ${eg.renk} p-6 text-center`}>
                  <span className="text-5xl">{eg.icon}</span>
                </div>
                <div className="p-4">
                  <h3 className="font-bold text-sm mb-1">{eg.baslik}</h3>
                  <p className="text-xs text-gray-500">{eg.aciklama}</p>
                  {egzersizPuanlari[eg.id] > 0 && <span className="inline-block mt-2 text-xs font-bold text-orange-600 bg-orange-50 px-2 py-1 rounded-full">🏆 +{egzersizPuanlari[eg.id]} puan</span>}
                </div>
              </div>
            ))}
          </div>
          <h3 className="text-sm font-bold text-gray-500 mb-3 uppercase tracking-wide">📖 Okuma Egzersizleri</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {egzersizler.filter(e => e.kat === 'okuma').map(eg => (
              <div key={eg.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden hover:shadow-md transition-shadow cursor-pointer" onClick={() => setAktifEgzersiz(eg.id)}>
                <div className={`bg-gradient-to-r ${eg.renk} p-6 text-center`}>
                  <span className="text-5xl">{eg.icon}</span>
                </div>
                <div className="p-4">
                  <h3 className="font-bold text-sm mb-1">{eg.baslik}</h3>
                  <p className="text-xs text-gray-500">{eg.aciklama}</p>
                  {egzersizPuanlari[eg.id] > 0 && <span className="inline-block mt-2 text-xs font-bold text-orange-600 bg-orange-50 px-2 py-1 rounded-full">🏆 +{egzersizPuanlari[eg.id]} puan</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div>
          <div className="flex items-center justify-between mb-4">
            <Button variant="outline" onClick={() => { durdur(); setAktifEgzersiz(null); }}>← Geri</Button>
            <h2 className="font-bold">{egzersizler.find(e => e.id === aktifEgzersiz)?.baslik}</h2>
            <div className="flex items-center gap-3">
              <span className={`text-lg font-bold ${kalanSure <= 5 ? 'text-red-500' : 'text-gray-700'}`}>{kalanSure}s</span>
              <Button size="sm" className={calisiyorMu ? 'bg-red-500' : 'bg-green-500'} onClick={() => calisiyorMu ? durdur() : baslat(aktifEgzersiz)}>
                {calisiyorMu ? '⏸ Durdur' : '▶ Başlat'}
              </Button>
            </div>
          </div>
          <div className="mb-4 p-4 bg-white rounded-xl border border-gray-200">
            <h4 className="text-sm font-semibold mb-3">⚙️ Ayarlar</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {aktifEgzersiz !== 'hizli-kelime' && (
                <div><label className="text-xs text-gray-500 block mb-1">Hız</label><input type="range" min="0.5" max="5" step="0.5" value={egzersizAyar.hiz} onChange={e => setEgzersizAyar({...egzersizAyar, hiz: parseFloat(e.target.value)})} className="w-full" /><span className="text-xs font-medium">{egzersizAyar.hiz}x</span></div>
              )}
              {['goz-takip','goz-sekiz','goz-zigzag'].includes(aktifEgzersiz) && (
                <div><label className="text-xs text-gray-500 block mb-1">Top Boyutu</label><input type="range" min="20" max="80" step="5" value={egzersizAyar.boyut} onChange={e => setEgzersizAyar({...egzersizAyar, boyut: parseInt(e.target.value)})} className="w-full" /><span className="text-xs font-medium">{egzersizAyar.boyut}px</span></div>
              )}
              <div><label className="text-xs text-gray-500 block mb-1">Süre (saniye)</label><input type="range" min="10" max="120" step="10" value={egzersizAyar.sure} onChange={e => setEgzersizAyar({...egzersizAyar, sure: parseInt(e.target.value)})} className="w-full" /><span className="text-xs font-medium">{egzersizAyar.sure}sn</span></div>
              {aktifEgzersiz === 'hizli-kelime' && (
                <div><label className="text-xs text-gray-500 block mb-1">Kelime Hızı</label><input type="range" min="100" max="800" step="50" value={egzersizAyar.kelimeHiz} onChange={e => setEgzersizAyar({...egzersizAyar, kelimeHiz: parseInt(e.target.value)})} className="w-full" /><span className="text-xs font-medium">{egzersizAyar.kelimeHiz} k/dk</span></div>
              )}
              {aktifEgzersiz === 'schulte' && (
                <div><label className="text-xs text-gray-500 block mb-1">Tablo Boyutu</label><input type="range" min="3" max="7" step="1" value={schulteSize} onChange={e => { setSchulteSize(parseInt(e.target.value)); }} className="w-full" /><span className="text-xs font-medium">{schulteSize}x{schulteSize}</span></div>
              )}
            </div>
          </div>
          {aktifEgzersiz === 'hizli-kelime' ? (
            <div className="bg-gray-900 rounded-2xl flex items-center justify-center" style={{height:'400px'}}>
              <div className="text-center">
                <div className="text-5xl font-bold text-white mb-4">{wpmKelimeler[wpmIndex] || ''}</div>
                <div className="text-gray-500 text-sm">{egzersizAyar.kelimeHiz} kelime/dakika • Kelime {wpmIndex + 1}/{wpmKelimeler.length}</div>
              </div>
            </div>
          ) : aktifEgzersiz === 'schulte' ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-4 flex flex-col items-center" style={{minHeight:'400px'}}>
              <div className="text-sm mb-3 text-gray-600">Sıradaki sayı: <span className="text-2xl font-bold text-amber-600">{schulteNext}</span> • Skor: <span className="font-bold text-green-600">{interSkor}</span></div>
              <div className="grid gap-1" style={{gridTemplateColumns: `repeat(${schulteSize}, 1fr)`}}>
                {schulteGrid.map((num, i) => (
                  <button key={i} className={`w-14 h-14 rounded-lg text-lg font-bold transition-all ${num < schulteNext ? 'bg-green-100 text-green-400' : 'bg-amber-50 border-2 border-amber-200 text-amber-800 hover:bg-amber-100 active:scale-95'}`}
                    disabled={num < schulteNext}
                    onClick={() => {
                      if (num === schulteNext) {
                        setSchulteNext(schulteNext + 1); setInterSkor(interSkor + 1);
                        if (schulteNext >= schulteSize * schulteSize) { yeniInterSoru('schulte'); }
                      }
                    }}>{num}</button>
                ))}
              </div>
            </div>
          ) : aktifEgzersiz === 'renk-eslestir' && renkSoru ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-6 flex flex-col items-center justify-center" style={{minHeight:'400px'}}>
              <div className="text-sm mb-2 text-gray-500">Yazının <strong>rengini</strong> seçin (yazdığını değil!)</div>
              <div className="text-6xl font-black mb-8" style={{color: renkSoru.renk}}>{renkSoru.yazi}</div>
              <div className="grid grid-cols-2 gap-3">
                {renkSoru.secenekler.map(r => (
                  <button key={r.ad} className="px-6 py-3 rounded-xl text-sm font-bold border-2 hover:scale-105 transition-all" style={{borderColor: r.hex, color: r.hex}}
                    onClick={() => {
                      if (r.ad === renkSoru.dogruRenk) {
                        setInterSkor(interSkor + 1);
                        const renkler = [{ad:'KIRMIZI',hex:'#ef4444'},{ad:'MAVİ',hex:'#3b82f6'},{ad:'YEŞİL',hex:'#22c55e'},{ad:'SARI',hex:'#eab308'},{ad:'TURUNCU',hex:'#f97316'},{ad:'MOR',hex:'#a855f7'}];
                        const r1 = renkler[Math.floor(Math.random()*renkler.length)];
                        const r2 = renkler[Math.floor(Math.random()*renkler.length)];
                        setRenkSoru({yazi:r1.ad, renk:r2.hex, dogruRenk:r2.ad, secenekler:renkler.sort(()=>Math.random()-0.5).slice(0,4)});
                      }
                    }}>{r.ad}</button>
                ))}
              </div>
              <div className="mt-4 text-lg font-bold text-green-600">Skor: {interSkor}</div>
            </div>
          ) : aktifEgzersiz === 'kelime-avcisi' ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-4" style={{minHeight:'400px'}}>
              <div className="text-center mb-3">
                <span className="text-sm text-gray-500">Hedef kelime: </span><span className="text-xl font-black text-sky-600 bg-sky-50 px-3 py-1 rounded-lg">{kelimeAvcisiHedef}</span>
                <span className="ml-3 text-sm text-green-600 font-bold">Bulunan: {kelimeAvcisiBulunan.size}</span>
              </div>
              <div className="flex flex-wrap gap-2 justify-center">
                {kelimeAvcisiMetin.map((k, i) => {
                  const isHedef = k === kelimeAvcisiHedef;
                  const bulundu = kelimeAvcisiBulunan.has(i);
                  return <button key={i} className={`px-2 py-1 rounded text-sm transition-all ${bulundu ? 'bg-green-500 text-white' : isHedef ? 'bg-white border border-gray-200 hover:bg-sky-100 cursor-pointer' : 'bg-white border border-gray-100 text-gray-600'}`}
                    onClick={() => { if (isHedef && !bulundu) { setKelimeAvcisiBulunan(new Set([...kelimeAvcisiBulunan, i])); setInterSkor(interSkor+1); } }}>{k}</button>;
                })}
              </div>
            </div>
          ) : aktifEgzersiz === 'ters-kelime' && interSoru ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-6 flex flex-col items-center justify-center" style={{minHeight:'400px'}}>
              <div className="text-sm text-gray-500 mb-2">Bu kelimeyi tersten okuyun ve yazın:</div>
              <div className="text-5xl font-black text-violet-600 mb-6 tracking-widest">{interSoru.ters}</div>
              <input className="border-2 border-violet-300 rounded-xl px-4 py-3 text-2xl text-center font-bold w-64 focus:outline-none focus:ring-2 focus:ring-violet-400" placeholder="Cevabınız..."
                value={interCevap} onChange={e => setInterCevap(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') {
                  if (interCevap.toLowerCase() === interSoru.kelime.toLowerCase()) {
                    setInterSkor(interSkor+1); setInterFeedback('dogru');
                    setTimeout(() => { const k = turkceKelimeler[Math.floor(Math.random()*turkceKelimeler.length)]; setInterSoru({kelime:k, ters:k.split('').reverse().join('')}); setInterCevap(''); setInterFeedback(null); }, 800);
                  } else { setInterFeedback('yanlis'); }
                }}} />
              {interFeedback && <div className={`mt-3 text-lg font-bold ${interFeedback === 'dogru' ? 'text-green-500' : 'text-red-500'}`}>{interFeedback === 'dogru' ? '✅ Doğru!' : '❌ Tekrar deneyin'}</div>}
              <div className="mt-4 text-sm font-bold text-green-600">Skor: {interSkor}</div>
            </div>
          ) : aktifEgzersiz === 'eksik-harf' && interSoru ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-6 flex flex-col items-center justify-center" style={{minHeight:'400px'}}>
              <div className="text-sm text-gray-500 mb-2">Eksik harfi tamamlayın:</div>
              <div className="text-5xl font-black text-cyan-600 mb-6 tracking-widest">{interSoru.gosterim}</div>
              <input className="border-2 border-cyan-300 rounded-xl px-4 py-3 text-2xl text-center font-bold w-32 focus:outline-none focus:ring-2 focus:ring-cyan-400" placeholder="?" maxLength={1}
                value={interCevap} onChange={e => {
                  const val = e.target.value;
                  setInterCevap(val);
                  if (val.length === 1) {
                    if (val.toLowerCase() === interSoru.kelime[interSoru.eksikIdx].toLowerCase()) {
                      setInterSkor(interSkor+1); setInterFeedback('dogru');
                      setTimeout(() => { const k = turkceKelimeler[Math.floor(Math.random()*turkceKelimeler.length)]; const idx = Math.floor(Math.random()*k.length); setInterSoru({kelime:k, eksikIdx:idx, gosterim:k.split('').map((h,i)=>i===idx?'_':h).join('')}); setInterCevap(''); setInterFeedback(null); }, 800);
                    } else { setInterFeedback('yanlis'); setTimeout(() => { setInterCevap(''); setInterFeedback(null); }, 600); }
                  }
                }} />
              {interFeedback && <div className={`mt-3 text-lg font-bold ${interFeedback === 'dogru' ? 'text-green-500' : 'text-red-500'}`}>{interFeedback === 'dogru' ? '✅ Doğru!' : '❌ Yanlış'}</div>}
              <div className="mt-4 text-sm font-bold text-green-600">Skor: {interSkor}</div>
            </div>
          ) : aktifEgzersiz === 'karisik-cumle' && interSoru ? (
            <div className="bg-white rounded-2xl border border-gray-200 p-6 flex flex-col items-center" style={{minHeight:'400px'}}>
              <div className="text-sm text-gray-500 mb-3">Kelimeleri doğru sıraya tıklayarak dizin:</div>
              <div className="min-h-[50px] border-2 border-dashed border-red-200 rounded-xl p-3 mb-4 w-full text-center">
                {interSoru.secilen.length > 0 ? <span className="text-lg font-medium text-gray-800">{interSoru.secilen.join(' ')}</span> : <span className="text-gray-400 text-sm">Kelimelere sırayla tıklayın...</span>}
              </div>
              <div className="flex flex-wrap gap-2 justify-center mb-4">
                {interSoru.karisik.map((k, i) => {
                  const used = interSoru.secilen.includes(k) && interSoru.secilen.filter(x => x === k).length > interSoru.karisik.slice(0, i).filter(x => x === k && interSoru.secilen.includes(x)).length;
                  return <button key={i} className={`px-4 py-2 rounded-xl text-sm font-bold border-2 transition-all ${interSoru.secilen[interSoru.secilen.length - 1] === k && interSoru.secilen.length === i + 1 ? 'opacity-40' : ''} ${interSoru.secilen.length > i ? 'bg-gray-100 text-gray-400 border-gray-200' : 'bg-red-50 border-red-300 text-red-700 hover:bg-red-100 cursor-pointer active:scale-95'}`}
                    onClick={() => {
                      if (interSoru.secilen.length <= i || !interSoru.secilen.includes(k)) {
                        const yeni = [...interSoru.secilen, k];
                        setInterSoru({...interSoru, secilen: yeni});
                        if (yeni.length === interSoru.karisik.length) {
                          if (yeni.join(' ') === interSoru.dogru) {
                            setInterSkor(interSkor + 1); setInterFeedback('dogru');
                            setTimeout(() => { yeniInterSoru('karisik-cumle'); setInterFeedback(null); }, 1200);
                          } else {
                            setInterFeedback('yanlis');
                            setTimeout(() => { setInterSoru({...interSoru, secilen: []}); setInterFeedback(null); }, 1000);
                          }
                        }
                      }
                    }}>{k}</button>;
                })}
              </div>
              <Button variant="outline" size="sm" onClick={() => setInterSoru({...interSoru, secilen: []})}>🔄 Sıfırla</Button>
              {interFeedback && <div className={`mt-3 text-lg font-bold ${interFeedback === 'dogru' ? 'text-green-500' : 'text-red-500'}`}>{interFeedback === 'dogru' ? '✅ Doğru cümle!' : '❌ Yanlış sıra, tekrar deneyin'}</div>}
              <div className="mt-2 text-sm font-bold text-green-600">Skor: {interSkor}</div>
            </div>
          ) : (
            <div className="bg-gray-50 rounded-2xl border border-gray-200 overflow-hidden" style={{height:'400px'}}>
              <canvas ref={canvasRef} className="w-full h-full" />
            </div>
          )}
          <div className="mt-3 text-center text-sm text-gray-500">
            {aktifEgzersiz === 'goz-takip' && 'Mavi topu gözlerinizle takip edin. Başınızı hareket ettirmeyin.'}
            {aktifEgzersiz === 'goz-sekiz' && 'Mor topu sonsuzluk (∞) şeklinde takip edin.'}
            {aktifEgzersiz === 'goz-zigzag' && 'Turuncu topu zigzag çizerek takip edin. Satır okuma hızınızı artırır.'}
            {aktifEgzersiz === 'goz-genisletme' && 'Kırmızı noktaya odaklanın, çevredeki harfleri okumaya çalışın.'}
            {aktifEgzersiz === 'hizli-kelime' && 'Kelimelere odaklanın. Geri dönüp okumayın, sadece ileriye bakın.'}
            {aktifEgzersiz === 'odaklanma' && 'Kırmızı noktaya odaklanın, çevredeki rakam/harfleri okumaya çalışın.'}
            {aktifEgzersiz === 'periferik' && 'Kırmızı noktaya odaklanıp çevredeki kelimeleri okumaya çalışın.'}
            {aktifEgzersiz === 'schulte' && 'Sayıları 1\'den başlayarak sırayla bulun. Gözünüzü merkeze sabit tutun.'}
            {aktifEgzersiz === 'goz-yoga' && 'Yeşil daire büyürken yakına, küçülürken uzağa odaklanın.'}
            {aktifEgzersiz === 'renk-eslestir' && 'Yazının anlamını değil, RENGINI seçin. Stroop etkisini yenin!'}
            {aktifEgzersiz === 'kelime-avcisi' && 'Hedef kelimeyi metinde bulup tıklayın. Hepsini bulun!'}
            {aktifEgzersiz === 'ters-kelime' && 'Kelimenin orijinalini yazıp Enter\'a basın.'}
            {aktifEgzersiz === 'eksik-harf' && 'Eksik harfi bulup yazın. Otomatik kontrol edilir.'}
            {aktifEgzersiz === 'karisik-cumle' && 'Kelimelere doğru sırayla tıklayarak cümleyi oluşturun.'}
          </div>
        </div>
      )}
    </div>
  );
}

function GirisAnaliziModul({ user, students, teachers }) {
  const { toast } = useToast();
  const [adim, setAdim] = useState("liste"); // liste, metin-sec, canli, sonuc, rapor-form, rapor-goruntule
  const [seciliOgrenci, setSeciliOgrenci] = useState(null);
  const [seciliMetin, setSeciliMetin] = useState(null);
  const [aktifOturumId, setAktifOturumId] = useState(null);
  const [sonuc, setSonuc] = useState(null);
  const [gecmisOturumlar, setGecmisOturumlar] = useState([]);
  const [aktifRapor, setAktifRapor] = useState(null);
  const [aktifOturum, setAktifOturum] = useState(null);
  const [normDialogAcik, setNormDialogAcik] = useState(false);
  const [metinDialogAcik, setMetinDialogAcik] = useState(false);

  const fetchGecmis = useCallback(async () => {
    try { const r = await axios.get(`${API}/diagnostic/sessions`); setGecmisOturumlar(r.data); } catch(e) {}
  }, []);

  useEffect(() => { fetchGecmis(); }, [fetchGecmis]);

  const analiziBaslat = async () => {
    if (!seciliOgrenci || !seciliMetin) { toast({ title: "Öğrenci ve metin seçin", variant: "destructive" }); return; }
    if (!seciliOgrenci?.id) { toast({ title: "Geçersiz öğrenci", description: "Lütfen listeden tekrar seçin", variant: "destructive" }); return; }
    if (!seciliMetin?.id) { toast({ title: "Geçersiz metin", description: "Lütfen metni tekrar seçin", variant: "destructive" }); return; }
    try {
      const payload = { ogrenci_id: seciliOgrenci.id, metin_id: seciliMetin.id };
      console.log("Session başlatılıyor:", payload);
      const r = await axios.post(`${API}/diagnostic/sessions`, payload);
      console.log("Session response:", r.data);
      if (!r.data?.id) throw new Error('Oturum ID alınamadı');
      setAktifOturumId(r.data.id);
      setAdim("canli");
    } catch(e) { console.error('Session error:', e.response?.data); toast({ title: "Hata", description: e.response?.data?.detail, variant: "destructive" }); }
  };

  const analiziTamamla = async (veri) => {
    // veri: { sure_saniye, hatalar, gozlem_notu, anlama, prozodik, ogretmen_notu, ogretmen_kur }
    try {
      const r = await axios.post(`${API}/diagnostic/sessions/${aktifOturumId}/complete`, {
        sure_saniye: veri.sure_saniye,
        hatalar: veri.hatalar,
        gozlem_notu: veri.gozlem_notu,
        ogretmen_kur: veri.ogretmen_kur,
      });
      setSonuc({ ...r.data, atanan_kur: veri.ogretmen_kur });
      fetchGecmis();
      if (veri.anlama && veri.prozodik) {
        try {
          const rRapor = await axios.post(`${API}/diagnostic/rapor`, {
            oturum_id: aktifOturumId,
            anlama: veri.anlama,
            prozodik: veri.prozodik,
            ogretmen_notu: veri.ogretmen_notu || "",
          });
          setAktifRapor(rRapor.data);
          setAdim("rapor-goruntule");
        } catch(e2) { setAdim("sonuc"); }
      } else { setAdim("sonuc"); }
    } catch(e) {
      toast({ title: "Hata", description: e.response?.data?.detail || "Analiz tamamlanamadı", variant: "destructive" });
    }
  };

  const kurOnayla = async (ogretmenKur) => {
    try {
      const r = await axios.post(`${API}/diagnostic/sessions/${aktifOturumId}/complete`, {
        ...sonuc, ogretmen_kur: ogretmenKur
      });
      toast({ title: "✅ Analiz kaydedildi!", description: `${seciliOgrenci.ad} → ${ogretmenKur} — Raporu doldurun` });
      fetchGecmis();
      setAktifOturum({ id: aktifOturumId, ...r.data, ogretmen_kur: ogretmenKur });
      setSonuc({ ...r.data, atanan_kur: ogretmenKur });
      setAdim("rapor-form");
    } catch(e) {
      // Güncelleme hatası olsa bile rapor formuna geç
      setAktifOturum({ id: aktifOturumId });
      setAdim("rapor-form");
    }
  };

  const hizLabel = { dusuk: "Düşük", orta: "Orta", yeterli: "Yeterli", ileri: "İleri" };
  const hizRenk = { dusuk: "bg-red-100 text-red-700", orta: "bg-yellow-100 text-yellow-700", yeterli: "bg-blue-100 text-blue-700", ileri: "bg-green-100 text-green-700" };

  // ── CANLI ANALİZ ──
  if (adim === "canli") {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => { setAdim("liste"); setAktifOturumId(null); }}>← Geri</Button>
          <h2 className="text-xl font-bold">Canlı Analiz</h2>
        </div>
        <CanlıAnalizEkrani ogrenci={seciliOgrenci} metin={seciliMetin} oturumId={aktifOturumId} onTamamla={analiziTamamla} user={user} />
      </div>
    );
  }

  // ── RAPOR FORMU ──
  if (adim === "rapor-form") {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => { setAdim("liste"); setSonuc(null); setSeciliOgrenci(null); setSeciliMetin(null); setAktifOturumId(null); }}>← Listeye Dön</Button>
          <span className="text-sm text-gray-500">Raporu doldurup kaydedin veya atlayın</span>
        </div>
        <RaporFormu
          oturum={aktifOturum || { id: aktifOturumId }}
          sonuc={sonuc || {}}
          ogrenci={seciliOgrenci || {}}
          metin={seciliMetin || {}}
          onRaporTamamla={(r) => { setAktifRapor(r); setAdim("rapor-goruntule"); }}
        />
      </div>
    );
  }

  // ── RAPOR GÖRÜNTÜLE ──
  if (adim === "rapor-goruntule" && aktifRapor) {
    return (
      <RaporGoruntule
        rapor={aktifRapor}
        ogrenci={seciliOgrenci || {}}
        onGeri={() => { setAdim("liste"); setAktifRapor(null); setSonuc(null); setSeciliOgrenci(null); setSeciliMetin(null); setAktifOturumId(null); }}
      />
    );
  }

  // ── SONUÇ ──
  if (adim === "sonuc" && sonuc) {
    return (
      <div className="space-y-4">
        <AnalizSonucEkrani sonuc={sonuc} ogrenci={seciliOgrenci} onKaydet={kurOnayla}
          onYeniAnaliz={() => { setAdim("liste"); setSonuc(null); }} />
      </div>
    );
  }

  // ── ANA LİSTE ──
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">Giriş Analizi</h2>
        <div className="flex gap-2">
          {(user.role === "admin" || user.role === "coordinator") && (
            <Button variant="outline" size="sm" onClick={() => setNormDialogAcik(true)}>
              ⚙️ Norm Tablosu
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={() => setMetinDialogAcik(true)}>
            📄 Metinler
          </Button>
        </div>
      </div>

      {/* Yeni Analiz Başlat */}
      <Card className="border-2 border-orange-200 shadow-sm">
        <CardHeader><CardTitle className="text-base flex items-center gap-2">🎯 Yeni Analiz Başlat</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label>Öğrenci Seç</Label>
              <Select value={seciliOgrenci?.id || ""} onValueChange={v => setSeciliOgrenci(students.find(s => s.id === v))}>
                <SelectTrigger><SelectValue placeholder="Öğrenci seçin..." /></SelectTrigger>
                <SelectContent position="popper" sideOffset={4} className="max-h-60 overflow-y-auto z-50">
                  {(students || []).map(s => <SelectItem key={s.id} value={s.id}>{s.ad} {s.soyad} — {s.sinif}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Analiz Metni Seç</Label>
              <button onClick={() => setMetinDialogAcik(true)}
                className="w-full border border-gray-300 rounded-lg p-2 text-left text-sm hover:border-orange-400 transition-colors">
                {seciliMetin ? <span className="font-medium">{seciliMetin.baslik} <span className="text-gray-400 font-normal">({seciliMetin.kelime_sayisi} kelime)</span></span> : <span className="text-gray-400">Metin seçmek için tıklayın...</span>}
              </button>
            </div>
          </div>
          <Button onClick={analiziBaslat} disabled={!seciliOgrenci || !seciliMetin}
            className="w-full bg-gradient-to-r from-orange-500 to-red-500 text-white py-3 font-bold">
            ▶ Analizi Başlat
          </Button>
        </CardContent>
      </Card>

      {/* Geçmiş Analizler */}
      <Card className="border-0 shadow-sm">
        <CardHeader><CardTitle className="text-base">Geçmiş Analizler</CardTitle></CardHeader>
        <CardContent>
          {gecmisOturumlar.length === 0 && <p className="text-gray-500 text-sm text-center py-8">Henüz analiz yapılmadı</p>}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Öğrenci</TableHead>
                <TableHead>Tarih</TableHead>
                <TableHead>WPM</TableHead>
                <TableHead>Doğruluk</TableHead>
                <TableHead>Hız</TableHead>
                <TableHead>Atanan Kur</TableHead>
                <TableHead>Rapor</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {gecmisOturumlar.filter(o => o.durum === "tamamlandi").map(o => {
                const ogr = students.find(s => s.id === o.ogrenci_id);
                return (
                  <TableRow key={o.id}>
                    <TableCell className="font-medium">{ogr ? `${ogr.ad} ${ogr.soyad}` : "-"}</TableCell>
                    <TableCell className="text-sm text-gray-500">{new Date(o.olusturma_tarihi).toLocaleDateString("tr-TR")}</TableCell>
                    <TableCell className="font-bold text-blue-600">{o.wpm}</TableCell>
                    <TableCell>%{o.dogruluk_yuzde}</TableCell>
                    <TableCell><span className={`px-2 py-1 rounded-full text-xs font-medium ${hizRenk[o.hiz_deger] || "bg-gray-100 text-gray-600"}`}>{hizLabel[o.hiz_deger] || "-"}</span></TableCell>
                    <TableCell className="font-semibold text-orange-600">{o.ogretmen_kur || "-"}</TableCell>
                    <TableCell>
                      <Button size="sm" variant="outline" onClick={async () => {
                        try { const r = await axios.get(`${API}/diagnostic/rapor/ogrenci/${o.ogrenci_id}`);
                          const ogrRapor = r.data.find(rp => rp.oturum_id === o.id);
                          if (ogrRapor) { setAktifRapor(ogrRapor); setSeciliOgrenci(students.find(s => s.id === o.ogrenci_id) || {}); setAdim("rapor-goruntule"); }
                          else { toast({ title: "Bu analiz için rapor bulunamadı" }); }
                        } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
                      }}>📄 Rapor</Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Norm Tablosu Dialog */}
      <Dialog open={normDialogAcik} onOpenChange={setNormDialogAcik}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>⚙️ Okuma Hızı Norm Tablosu</DialogTitle>
            <DialogDescription>Sınıf bazlı okuma hızı sınır değerlerini düzenleyin (kelime/dakika)</DialogDescription>
          </DialogHeader>
          <NormTablosu onClose={() => setNormDialogAcik(false)} />
        </DialogContent>
      </Dialog>

      {/* Metin Seçim Dialog */}
      <Dialog open={metinDialogAcik} onOpenChange={setMetinDialogAcik}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>📄 Analiz Metinleri</DialogTitle>
            <DialogDescription>{seciliMetin ? "Farklı bir metin seçin veya yeni metin ekleyin" : "Analiz için metin seçin"}</DialogDescription>
          </DialogHeader>
          <MetinYonetimi secimModu={true} user={user} onMetinSec={m => { setSeciliMetin(m); setMetinDialogAcik(false); }} />
        </DialogContent>
      </Dialog>
    </div>
  );
}




// ═══════════════════════════════════════════════
// ÖĞRETMEN PANELİ — Sadece kendi öğrencileri, görev, analiz, mesaj
// ═══════════════════════════════════════════════

function OgretmenPaneli({ user, logout }) {
  const { toast } = useToast();
  const [aktifSekme, setAktifSekme] = useState("dashboard");
  const [ogrenciler, setOgrenciler] = useState([]);
  const [riskler, setRiskler] = useState([]);
  const [gorevler, setGorevler] = useState([]);
  const [mesajlar, setMesajlar] = useState([]);
  const [okunmamisSayisi, setOkunmamisSayisi] = useState(0);
  const [kullanicilar, setKullanicilar] = useState([]);
  const [seciliOgrenci, setSeciliOgrenci] = useState(null);
  const [ogrenciDetay, setOgrenciDetay] = useState(null);
  // AI Koçluk state'leri
  const [aiRapor, setAiRapor] = useState(null);
  const [aiYukleniyor, setAiYukleniyor] = useState(false);
  const [aiDna, setAiDna] = useState(null);
  const [aiAcikKart, setAiAcikKart] = useState(null);
  // Görev atama
  const [gorevForm, setGorevForm] = useState({ baslik: "", aciklama: "", tur: "ozel", son_tarih: "", film_link: "", makale_link: "", kitap_yazar: "" });
  const [gorevHedefler, setGorevHedefler] = useState([]);
  const [gorevAtaGoster, setGorevAtaGoster] = useState(false);
  // Rozet + Anket
  const [rozetlerim, setRozetlerim] = useState([]);
  const [rozetTanimlari, setRozetTanimlari] = useState([]);
  const [anketOzet, setAnketOzet] = useState(null);
  const [rozetDetayAcik, setRozetDetayAcik] = useState(false);
  const [seciliRozet, setSeciliRozet] = useState(null);
  const [anketDetayAcik, setAnketDetayAcik] = useState(false);
  const [seciliKategori, setSeciliKategori] = useState(null);
  // Hedef sistemi
  const [hedefler, setHedefler] = useState([]);
  const [hedefEkleAcik, setHedefEkleAcik] = useState(false);
  const [hedefForm, setHedefForm] = useState({ kod: "", hedef_deger: 0, son_tarih: "" });
  // Mesaj
  const [mesajAlici, setMesajAlici] = useState("");
  const [mesajForm, setMesajForm] = useState({ konu: "", icerik: "" });
  const [mesajGorunum, setMesajGorunum] = useState("gelen");

  const ogretmenId = user.linked_id || user.id;

  const fetchAll = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/risk-skor/toplu`);
      const data = Array.isArray(r.data) ? r.data : [];
      setRiskler(data.filter(s => s.ogretmen_id === ogretmenId));
    } catch(e) { setRiskler([]); }
    try {
      const sr = await axios.get(`${API}/students`);
      const data = Array.isArray(sr.data) ? sr.data : [];
      setOgrenciler(data.filter(s => s.ogretmen_id === ogretmenId && !s.arsivli));
    } catch(e) { setOgrenciler([]); }
    try { const r = await axios.get(`${API}/gorevler`); setGorevler(Array.isArray(r.data) ? r.data : []); } catch(e) { setGorevler([]); }
    try { const r = await axios.get(`${API}/mesajlar`); setMesajlar(Array.isArray(r.data) ? r.data : []); } catch(e) { setMesajlar([]); }
    try { const r = await axios.get(`${API}/mesajlar/okunmamis-sayisi`); setOkunmamisSayisi(r.data?.sayi || 0); } catch(e) {}
    try { const r = await axios.get(`${API}/auth/users`); setKullanicilar(Array.isArray(r.data) ? r.data : []); } catch(e) { setKullanicilar([]); }
    try { await axios.post(`${API}/rozetler/kontrol`); } catch(e) {}
    try { const r = await axios.get(`${API}/rozetler/${user.id}`); setRozetlerim(Array.isArray(r.data) ? r.data : []); } catch(e) {}
    try { const r = await axios.get(`${API}/rozetler/tanim`); setRozetTanimlari(r.data?.ogretmen || []); } catch(e) {}
    try { const r = await axios.get(`${API}/anketler/ogretmen/${ogretmenId}/ozet`); setAnketOzet(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/hedefler`); setHedefler(Array.isArray(r.data) ? r.data : []); } catch(e) {}
  }, [ogretmenId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Öğrenci detayını çek
  const ogrenciDetayCek = async (ogrenci) => {
    setSeciliOgrenci(ogrenci);
    setAiRapor(null); setAiDna(null); setAiAcikKart(null); // AI state reset
    try {
      const [logR, statR, riskR, xpR, gorevR] = await Promise.all([
        axios.get(`${API}/reading-logs/${ogrenci.id}`),
        axios.get(`${API}/reading-logs/${ogrenci.id}/istatistik`),
        axios.get(`${API}/risk-skor/${ogrenci.id}`),
        axios.get(`${API}/xp/durum/${ogrenci.id}`).catch(() => ({ data: null })),
        axios.get(`${API}/gorevler?hedef_id=${ogrenci.id}&hedef_tip=ogrenci`),
      ]);
      setOgrenciDetay({ logs: logR.data, stat: statR.data, risk: riskR.data, xp: xpR.data, gorevler: gorevR.data });
    } catch(e) { setOgrenciDetay(null); }
    setAktifSekme("ogrenci-detay");
  };

  // Görev ata
  const gorevAta = async (e) => {
    e.preventDefault();
    if (gorevHedefler.length === 0) { toast({ title: "Öğrenci seçin", variant: "destructive" }); return; }
    try {
      if (gorevHedefler.length === 1) {
        await axios.post(`${API}/gorevler`, { ...gorevForm, hedef_id: gorevHedefler[0], hedef_tip: "ogrenci" });
      } else {
        await axios.post(`${API}/gorevler/toplu`, { hedef_idler: gorevHedefler, hedef_tip: "ogrenci", gorev: gorevForm });
      }
      toast({ title: `✅ ${gorevHedefler.length} öğrenciye görev atandı` });
      setGorevForm({ baslik: "", aciklama: "", tur: "ozel", son_tarih: "", film_link: "", makale_link: "", kitap_yazar: "" });
      setGorevHedefler([]); setGorevAtaGoster(false); fetchAll();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  // Mesaj gönder
  const mesajGonder = async (e) => {
    e.preventDefault();
    if (!mesajAlici) { toast({ title: "Alıcı seçin", variant: "destructive" }); return; }
    try {
      await axios.post(`${API}/mesajlar`, { alici_id: mesajAlici, konu: mesajForm.konu, icerik: mesajForm.icerik });
      toast({ title: "✉️ Mesaj gönderildi!" }); setMesajForm({ konu: "", icerik: "" }); setMesajAlici(""); fetchAll();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };
  const mesajOkundu = async (id) => { try { await axios.put(`${API}/mesajlar/${id}/okundu`); fetchAll(); } catch(e) {} };

  const benimGorevlerim = gorevler.filter(g => g.hedef_id === user.id);
  const atadiklarim = gorevler.filter(g => g.atayan_id === user.id);
  const gelenMesajlar = mesajlar.filter(m => m.alici_id === user.id);
  const gidenMesajlar = mesajlar.filter(m => m.gonderen_id === user.id);

  const riskRenk = (s) => s === "yuksek" ? "bg-red-100 text-red-700" : s === "orta" ? "bg-yellow-100 text-yellow-700" : "bg-green-100 text-green-700";
  const riskIcon = (s) => s === "yuksek" ? "🔴" : s === "orta" ? "🟡" : "🟢";

  const sekmeler = [
    { id: "dashboard", label: "Dashboard", icon: "📊" },
    { id: "ogrencilerim", label: "Öğrencilerim", icon: "👥" },
    { id: "gorevler", label: "Görevler", icon: "📌", badge: benimGorevlerim.filter(g => g.durum !== "tamamlandi").length || null },
    { id: "giris-analizi", label: "Analiz", icon: "🔬" },
    { id: "gelisim", label: "Gelişim", icon: "🎓" },
    { id: "mesajlar", label: "Mesajlar", icon: "✉️", badge: okunmamisSayisi || null },
  ];

  // ── ÖĞRENCİ DETAY ──
  if (aktifSekme === "ogrenci-detay" && seciliOgrenci) {
    const d = ogrenciDetay;
    return (
      <div className="min-h-screen bg-gray-50">
        <div className="bg-white border-b sticky top-0 z-10"><div className="max-w-4xl mx-auto px-4 py-3 flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => setAktifSekme("ogrencilerim")}>← Geri</Button>
          <div><div className="font-bold">{seciliOgrenci.ad} {seciliOgrenci.soyad}</div><div className="text-xs text-gray-500">{seciliOgrenci.sinif}. sınıf • {seciliOgrenci.kur || "Kur yok"}</div></div>
        </div></div>
        <div className="max-w-4xl mx-auto p-4 space-y-4">
          {d ? (<>
            {/* Risk + İstatistik */}
            <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
              <div className={`rounded-2xl p-3 text-center border ${riskRenk(d.risk?.seviye)}`}><div className="text-2xl font-bold">{d.risk?.risk_skoru || 0}</div><div className="text-xs">{riskIcon(d.risk?.seviye)} Risk</div></div>
              <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-orange-600">{d.stat?.streak || 0}</div><div className="text-xs text-gray-500">🔥 Streak</div></div>
              <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-green-600">{d.stat?.bugun_dakika || 0}</div><div className="text-xs text-gray-500">⏱ Bugün</div></div>
              <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-blue-600">{d.stat?.toplam_kitap || 0}</div><div className="text-xs text-gray-500">📚 Kitap</div></div>
              <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-purple-600">{d.xp?.toplam_xp || 0}</div><div className="text-xs text-gray-500">{d.xp?.lig_label || "XP"}</div></div>
            </div>
            {/* Risk faktörleri */}
            {d.risk?.faktorler?.length > 0 && (<div className="bg-red-50 rounded-xl p-3 border border-red-100"><div className="text-xs font-medium text-red-700 mb-1">⚠️ Risk Faktörleri:</div>{d.risk.faktorler.map((f,i) => <div key={i} className="text-xs text-red-600">• {f}</div>)}</div>)}

            {/* 🤖 AI Koçluk Butonu + Sonuçlar */}
            {(() => {
              const aiKoclukAl = async () => {
                setAiYukleniyor(true);
                try {
                  const [kocR, dnaR] = await Promise.all([
                    axios.post(`${API}/ai/kocluk/${seciliOgrenci.id}`),
                    axios.get(`${API}/ai/dna/${seciliOgrenci.id}`),
                  ]);
                  setAiRapor(kocR.data);
                  setAiDna(dnaR.data);
                } catch(e) { toast({ title: e.response?.data?.detail || "AI hatası. ANTHROPIC_API_KEY tanımlı mı?", variant: "destructive" }); }
                setAiYukleniyor(false);
              };

              const analiz = aiRapor?.ai_analiz;
              const dnaB = aiDna?.boyutlar || {};
              const dnaRenk = (v) => v >= 70 ? "bg-green-500" : v >= 40 ? "bg-yellow-500" : "bg-red-500";

              return (<div className="space-y-3">
                {!aiRapor && (
                  <button onClick={aiKoclukAl} disabled={aiYukleniyor}
                    className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-2xl p-4 shadow-md hover:shadow-lg transition-all disabled:opacity-60">
                    <div className="flex items-center justify-center gap-2">
                      {aiYukleniyor ? (<><div className="animate-spin h-5 w-5 border-2 border-white border-t-transparent rounded-full" /><span className="text-sm">AI analiz ediyor...</span></>) : (<><span className="text-xl">🤖</span><span className="font-bold">AI Koçluk Önerisi Al</span></>)}
                    </div>
                    {!aiYukleniyor && <div className="text-xs opacity-80 mt-1">7 boyutlu DNA profili + kişiselleştirilmiş müdahale planı</div>}
                  </button>
                )}

                {aiDna && (<div className="bg-white rounded-2xl p-4 shadow-sm border">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2"><span className="text-lg">🧬</span><span className="font-bold text-sm">Okuma DNA'sı</span><span className="text-xs bg-cyan-100 text-cyan-700 px-2 py-0.5 rounded-full">{aiDna.profil_label}</span></div>
                    <button onClick={() => { setAiRapor(null); setAiDna(null); }} className="text-xs text-gray-400 hover:text-red-400">Yenile ↻</button>
                  </div>
                  <div className="space-y-1.5">
                    {[
                      ["Kelime Gücü", dnaB.kelime_gucu, "📚"],
                      ["Akıcılık", dnaB.akicilik, "⚡"],
                      ["Anlama Derinliği", dnaB.anlama_derinligi, "🧠"],
                      ["Dikkat Süresi", dnaB.dikkat_suresi, "🎯"],
                      ["Zorluk Toleransı", dnaB.zorluk_toleransi, "💪"],
                    ].map(([ad, val, ikon]) => (
                      <div key={ad} className="flex items-center gap-2">
                        <span className="text-xs">{ikon}</span>
                        <span className="text-[10px] text-gray-500 w-24">{ad}</span>
                        <div className="flex-1 bg-gray-100 rounded-full h-2"><div className={`h-2 rounded-full transition-all ${dnaRenk(val)}`} style={{width:`${val}%`}} /></div>
                        <span className="text-[10px] font-bold w-8 text-right">{val}</span>
                      </div>
                    ))}
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs">🔮</span><span className="text-[10px] text-gray-500 w-24">Psikoloji</span>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${dnaB.okuma_psikolojisi === 'keşifçi' ? 'bg-green-100 text-green-700' : dnaB.okuma_psikolojisi === 'kararsız' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>{dnaB.okuma_psikolojisi || "—"}</span>
                    </div>
                  </div>
                </div>)}

                {analiz && typeof analiz === 'object' && (<>
                  {/* Accordion kartlar */}
                  {[
                    ["durum", "📊 Durum Değerlendirmesi", analiz.durum_degerlendirmesi],
                    ["risk", "🚨 Risk Analizi + Müdahale", analiz.risk_analizi],
                    ["plan", "📋 4 Haftalık Plan", analiz.mudahale_plani],
                    ["mesaj", "✉️ Veliye Mesaj Taslağı", analiz.veliye_mesaj],
                    ["gorev", "📌 Haftalık Görev Önerisi", analiz.haftalik_gorevler],
                    ["kitap", "📚 Kitap Tavsiyeleri", analiz.kitap_tavsiyeleri],
                    ["motivasyon", "💬 Motivasyon", analiz.motivasyon_mesaji],
                    ["kelime", "📝 Kelime Planı", analiz.kelime_mudahale],
                    ["recete", "🎯 Metin Reçetesi", analiz.metin_recetesi],
                  ].filter(([,, v]) => v).map(([key, baslik, icerik]) => (
                    <div key={key} className="bg-white rounded-xl border shadow-sm overflow-hidden">
                      <button className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50" onClick={() => setAiAcikKart(aiAcikKart === key ? null : key)}>
                        <span className="text-sm font-medium">{baslik}</span>
                        <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${aiAcikKart === key ? 'rotate-180' : ''}`} />
                      </button>
                      {aiAcikKart === key && (<div className="px-4 pb-3 text-xs text-gray-600 border-t">
                        {typeof icerik === 'string' ? (
                          key === 'mesaj' ? (<div className="mt-2 space-y-2"><p className="whitespace-pre-wrap bg-blue-50 p-3 rounded-lg">{icerik}</p><Button size="sm" className="bg-blue-600 text-white text-xs" onClick={() => { setMesajForm({ konu: "Okuma gelişimi hakkında", icerik }); setMesajAlici(seciliOgrenci.veli_id || ""); setAktifSekme("mesajlar"); }}>✉️ Bu Mesajı Gönder</Button></div>)
                          : <p className="mt-2 whitespace-pre-wrap">{icerik}</p>
                        ) : Array.isArray(icerik) ? (
                          <div className="mt-2 space-y-1">{icerik.map((item, i) => (<div key={i} className="bg-gray-50 p-2 rounded-lg">{typeof item === 'string' ? item : JSON.stringify(item, null, 0).replace(/[{}"]/g, '').replace(/,/g, ' • ')}</div>))}</div>
                        ) : typeof icerik === 'object' ? (
                          <div className="mt-2 space-y-1">{Object.entries(icerik).map(([k, v]) => (<div key={k} className="flex gap-2"><span className="font-medium text-gray-700 min-w-[80px]">{k}:</span><span>{typeof v === 'string' ? v : JSON.stringify(v)}</span></div>))}</div>
                        ) : <p className="mt-2">{String(icerik)}</p>}
                      </div>)}
                    </div>
                  ))}
                  <div className="text-[9px] text-gray-300 text-center">AI analizi {new Date(aiRapor.tarih).toLocaleString('tr-TR')} • {aiRapor.token} token • ${aiRapor.maliyet?.toFixed(4)}</div>
                </>)}

                {analiz && typeof analiz === 'string' && (<div className="bg-white rounded-xl p-4 border shadow-sm"><div className="text-xs text-gray-600 whitespace-pre-wrap">{analiz}</div></div>)}
              </div>);
            })()}

            {/* Haftalık */}
            <div className="bg-white rounded-2xl p-4 shadow-sm border"><div className="flex items-center justify-between mb-2"><span className="text-sm font-medium">Haftalık Aktivite</span><span className="font-bold">{d.stat?.aktif_gunler_7 || 0}/4 gün</span></div><div className="flex gap-1">{[0,1,2,3].map(i => (<div key={i} className={`flex-1 h-3 rounded-full ${i < (d.stat?.aktif_gunler_7 || 0) ? 'bg-gradient-to-r from-orange-400 to-red-500' : 'bg-gray-100'}`} />))}</div></div>
            {/* Görevler */}
            {d.gorevler?.length > 0 && (<div><h3 className="font-bold text-sm mb-2">📌 Görevler ({d.gorevler.length})</h3>{d.gorevler.slice(0,5).map(g => (<div key={g.id} className="bg-white rounded-xl p-3 shadow-sm border mb-2 flex items-center justify-between"><div className="text-sm">{g.baslik}</div><span className={`text-xs px-2 py-0.5 rounded-full ${g.durum === "tamamlandi" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>{g.durum === "tamamlandi" ? "✅" : "⏳"} {g.durum}</span></div>))}</div>)}
            {/* Son okumalar */}
            {d.logs?.length > 0 && (<div><h3 className="font-bold text-sm mb-2">📖 Son Okumalar</h3>{d.logs.slice(0,8).map(l => (<div key={l.id} className="bg-white rounded-xl p-3 shadow-sm border mb-2 flex items-center justify-between"><div><div className="text-sm font-medium">{l.kitap_adi || "—"}</div><div className="text-xs text-gray-400">{l.bolum} • {l.sure_dakika} dk</div></div><div className="text-xs text-gray-400">{new Date(l.tarih).toLocaleDateString('tr-TR')}</div></div>))}</div>)}
          </>) : (<div className="text-center py-12 text-gray-500">Yükleniyor...</div>)}
        </div>
        <Toaster />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center"><BookOpen className="h-5 w-5 text-white" /></div>
            <div><div className="font-bold text-gray-900">{user.ad} {user.soyad}</div><div className="text-xs text-gray-500">Öğretmen • {ogrenciler.length} öğrenci</div></div>
          </div>
          <div className="flex items-center gap-2">
            <BildirimZili user={user} />
            <Button variant="outline" size="sm" onClick={logout}><LogOut className="h-3 w-3 mr-1" />Çıkış</Button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b sticky top-[60px] z-10">
        <div className="max-w-4xl mx-auto px-2 flex gap-1 overflow-x-auto py-2">
          {sekmeler.map(s => (
            <button key={s.id} onClick={() => setAktifSekme(s.id)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium whitespace-nowrap transition-all ${aktifSekme === s.id ? 'bg-blue-600 text-white shadow' : 'text-gray-600 hover:bg-gray-100'}`}>
              {s.icon} {s.label} {s.badge > 0 && <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${aktifSekme === s.id ? 'bg-white/30' : 'bg-red-100 text-red-600'}`}>{s.badge}</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-4xl mx-auto p-4 space-y-4">

        {/* ═══ DASHBOARD ═══ */}
        {aktifSekme === "dashboard" && (<>
          {/* Motivasyon cümlesi — her girişte değişir */}
          {(() => {
            const motivasyonlar = [
              { emoji: "🌟", cumle: "Bugün bir öğrencinizin gözlerindeki ışığı parlatabiirsiniz. Her kur atlama, bir hayatı değiştiren adımdır.", renk: "from-amber-50 to-orange-50 border-amber-200" },
              { emoji: "🚀", cumle: "Öğrencilerinizin potansiyeli sınırsız — sizin rehberliğiniz onları bir adım öteye taşıyor.", renk: "from-blue-50 to-indigo-50 border-blue-200" },
              { emoji: "📚", cumle: "Her okunan sayfa bir tohum, her kur atlama bir çiçek. Bahçenizi büyütmeye devam edin!", renk: "from-green-50 to-emerald-50 border-green-200" },
              { emoji: "💪", cumle: "Riskli öğrenci yoktur, henüz keşfedilmemiş potansiyel vardır. Bugün kiminle başlayacaksınız?", renk: "from-purple-50 to-pink-50 border-purple-200" },
              { emoji: "🎯", cumle: "Küçük adımlar büyük dönüşümler yaratır. Bugün bir görev atayarak fark yaratın!", renk: "from-teal-50 to-cyan-50 border-teal-200" },
              { emoji: "🔥", cumle: "Streak'ler sadece öğrenciler için değil — sizin de tutarlılığınız onlara ilham veriyor.", renk: "from-red-50 to-orange-50 border-red-200" },
              { emoji: "🌱", cumle: "Sabır ve kararlılıkla ektiğiniz her tohum, zamanı geldiğinde meyve verecek.", renk: "from-lime-50 to-green-50 border-lime-200" },
              { emoji: "🏅", cumle: "Her rozet kazandığınızda, öğrencilerinize 'sürekli gelişim' modelini gösteriyorsunuz.", renk: "from-yellow-50 to-amber-50 border-yellow-200" },
              { emoji: "💡", cumle: "Bir çocuğa okumayı sevdirmek, ona ömür boyu sürecek bir süper güç vermektir.", renk: "from-indigo-50 to-blue-50 border-indigo-200" },
              { emoji: "🌈", cumle: "Bugün sınıfınızdaki en sessiz öğrenciye bir kitap önerin — belki de en çok ona ihtiyacı var.", renk: "from-pink-50 to-rose-50 border-pink-200" },
              { emoji: "🎓", cumle: "Kur atlatan her öğrenci, sizin eğitimci kimliğinizin en güçlü kanıtıdır.", renk: "from-violet-50 to-purple-50 border-violet-200" },
              { emoji: "📖", cumle: "Okuma alışkanlığı bir günde değil, sizin gibi kararlı eğitimcilerin rehberliğinde oluşur.", renk: "from-sky-50 to-blue-50 border-sky-200" },
              { emoji: "⭐", cumle: "Veliler size güveniyor, öğrenciler size bakıyor. Bu güvenin hakkını her gün veriyorsunuz.", renk: "from-amber-50 to-yellow-50 border-amber-200" },
              { emoji: "🧭", cumle: "Her analiz raporu bir pusula, her görev bir yol haritası. Öğrencilerinizi hedefe taşıyın!", renk: "from-emerald-50 to-teal-50 border-emerald-200" },
            ];
            const gunIndex = Math.floor(Date.now() / (1000 * 60 * 60)) % motivasyonlar.length;
            const m = motivasyonlar[gunIndex];
            return (
              <div className={`bg-gradient-to-r ${m.renk} rounded-2xl p-4 border`}>
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{m.emoji}</span>
                  <p className="text-sm text-gray-700 italic leading-relaxed">{m.cumle}</p>
                </div>
              </div>
            );
          })()}

          {/* Özet kartlar */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl p-4 text-white">
              <div className="text-3xl font-bold">{ogrenciler.length}</div>
              <div className="text-xs opacity-80">👥 Toplam Öğrenci</div>
            </div>
            <div className="bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl p-4 text-white">
              <div className="text-3xl font-bold">{riskler.filter(r => r.aktif_gunler_7 >= 4).length}</div>
              <div className="text-xs opacity-80">✅ Hedefte ({riskler.length > 0 ? Math.round(riskler.filter(r => r.aktif_gunler_7 >= 4).length / riskler.length * 100) : 0}%)</div>
            </div>
            <div className="bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl p-4 text-white">
              <div className="text-3xl font-bold">{atadiklarim.filter(g => g.durum === "bekliyor").length}</div>
              <div className="text-xs opacity-80">📌 Bekleyen Görev</div>
            </div>
            <div className="bg-gradient-to-br from-purple-500 to-pink-500 rounded-2xl p-4 text-white">
              <div className="text-3xl font-bold">{okunmamisSayisi}</div>
              <div className="text-xs opacity-80">✉️ Okunmamış Mesaj</div>
            </div>
          </div>

          {/* Risk dağılımı */}
          {riskler.length > 0 && (
            <Card className="border-0 shadow-sm">
              <CardHeader className="pb-2"><CardTitle className="text-base">📊 Öğrenci Risk Dağılımı</CardTitle></CardHeader>
              <CardContent>
                <div className="grid grid-cols-3 gap-3 mb-4">
                  <div className="bg-green-50 rounded-xl p-3 text-center border border-green-200">
                    <div className="text-2xl font-bold text-green-700">{riskler.filter(r => r.risk_seviye === "dusuk").length}</div>
                    <div className="text-xs text-green-600">🟢 Düşük Risk</div>
                    <div className="text-[10px] text-gray-400">Düzenli okuyor</div>
                  </div>
                  <div className="bg-yellow-50 rounded-xl p-3 text-center border border-yellow-200">
                    <div className="text-2xl font-bold text-yellow-700">{riskler.filter(r => r.risk_seviye === "orta").length}</div>
                    <div className="text-xs text-yellow-600">🟡 Orta Risk</div>
                    <div className="text-[10px] text-gray-400">Takip gerekli</div>
                  </div>
                  <div className="bg-red-50 rounded-xl p-3 text-center border border-red-200">
                    <div className="text-2xl font-bold text-red-700">{riskler.filter(r => r.risk_seviye === "yuksek").length}</div>
                    <div className="text-xs text-red-600">🔴 Yüksek Risk</div>
                    <div className="text-[10px] text-gray-400">Müdahale gerekli</div>
                  </div>
                </div>
                {/* İlerleme çubuğu */}
                <div className="flex h-4 rounded-full overflow-hidden">
                  {riskler.filter(r => r.risk_seviye === "dusuk").length > 0 && <div className="bg-green-500 transition-all" style={{ width: `${riskler.filter(r => r.risk_seviye === "dusuk").length / riskler.length * 100}%` }} />}
                  {riskler.filter(r => r.risk_seviye === "orta").length > 0 && <div className="bg-yellow-400 transition-all" style={{ width: `${riskler.filter(r => r.risk_seviye === "orta").length / riskler.length * 100}%` }} />}
                  {riskler.filter(r => r.risk_seviye === "yuksek").length > 0 && <div className="bg-red-500 transition-all" style={{ width: `${riskler.filter(r => r.risk_seviye === "yuksek").length / riskler.length * 100}%` }} />}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Yüksek riskli öğrenciler */}
          {riskler.filter(r => r.risk_seviye === "yuksek").length > 0 && (
            <Card className="border-0 shadow-sm border-l-4 border-l-red-500">
              <CardHeader className="pb-2"><CardTitle className="text-sm text-red-700">🚨 Acil Müdahale Gerekli</CardTitle></CardHeader>
              <CardContent><div className="space-y-2">
                {riskler.filter(r => r.risk_seviye === "yuksek").map(r => (
                  <div key={r.id} className="flex items-center justify-between p-2.5 bg-red-50 rounded-xl cursor-pointer hover:bg-red-100 transition-all" onClick={() => ogrenciDetayCek(r)}>
                    <div className="flex items-center gap-2"><div className="w-8 h-8 bg-red-100 rounded-full flex items-center justify-center text-sm">🔴</div><div><div className="font-medium text-sm">{r.ad} {r.soyad}</div><div className="text-[10px] text-gray-500">{r.sinif}. sınıf</div></div></div>
                    <div className="text-right"><div className="text-xs text-red-600 font-bold">Risk: {r.risk_skoru}</div><div className="text-[10px] text-gray-400">Streak: {r.streak} • 7g: {r.dakika_7}dk</div></div>
                  </div>
                ))}
              </div></CardContent>
            </Card>
          )}

          {/* Genel istatistikler */}
          {riskler.length > 0 && (
            <div className="grid grid-cols-2 gap-3">
              <Card className="border-0 shadow-sm"><CardContent className="p-4">
                <div className="text-xs text-gray-500 mb-1">📖 Ortalama Haftalık Okuma</div>
                <div className="text-2xl font-bold text-blue-600">{riskler.length > 0 ? Math.round(riskler.reduce((t, r) => t + r.dakika_7, 0) / riskler.length) : 0} dk</div>
                <div className="text-[10px] text-gray-400">öğrenci başına / hafta</div>
              </CardContent></Card>
              <Card className="border-0 shadow-sm"><CardContent className="p-4">
                <div className="text-xs text-gray-500 mb-1">🔥 Ortalama Streak</div>
                <div className="text-2xl font-bold text-orange-600">{riskler.length > 0 ? Math.round(riskler.reduce((t, r) => t + r.streak, 0) / riskler.length * 10) / 10 : 0} gün</div>
                <div className="text-[10px] text-gray-400">öğrenci başına</div>
              </CardContent></Card>
              <Card className="border-0 shadow-sm"><CardContent className="p-4">
                <div className="text-xs text-gray-500 mb-1">⭐ Toplam XP</div>
                <div className="text-2xl font-bold text-purple-600">{riskler.reduce((t, r) => t + (r.toplam_xp || 0), 0)}</div>
                <div className="text-[10px] text-gray-400">tüm öğrenciler</div>
              </CardContent></Card>
              <Card className="border-0 shadow-sm"><CardContent className="p-4">
                <div className="text-xs text-gray-500 mb-1">📌 Görev Tamamlama</div>
                <div className="text-2xl font-bold text-green-600">{atadiklarim.length > 0 ? Math.round(atadiklarim.filter(g => g.durum === "tamamlandi").length / atadiklarim.length * 100) : 0}%</div>
                <div className="text-[10px] text-gray-400">{atadiklarim.filter(g => g.durum === "tamamlandi").length}/{atadiklarim.length} görev</div>
              </CardContent></Card>
            </div>
          )}

          {/* Bana atanan görevler */}
          {benimGorevlerim.filter(g => g.durum !== "tamamlandi").length > 0 && (
            <Card className="border-0 shadow-sm border-l-4 border-l-indigo-500">
              <CardHeader className="pb-2"><CardTitle className="text-sm text-indigo-700">📌 Yöneticiden Gelen Görevlerim</CardTitle></CardHeader>
              <CardContent><div className="space-y-2">
                {benimGorevlerim.filter(g => g.durum !== "tamamlandi").map(g => (
                  <div key={g.id} className="flex items-center justify-between p-2 bg-indigo-50 rounded-xl">
                    <div><div className="font-medium text-sm">{g.baslik}</div><div className="text-[10px] text-gray-500">Atayan: {g.atayan_ad}{g.son_tarih && ` • Son: ${new Date(g.son_tarih).toLocaleDateString('tr-TR')}`}</div></div>
                    <Button size="sm" className="bg-green-600 text-white text-xs h-7" onClick={async () => { try { await axios.put(`${API}/gorevler/${g.id}/durum`, { durum: "tamamlandi" }); toast({ title: "✅ Tamamlandı" }); fetchAll(); } catch(e) {} }}>Tamamla</Button>
                  </div>
                ))}
              </div></CardContent>
            </Card>
          )}

          {/* Öğrenci sıralaması */}
          {riskler.length > 0 && (
            <Card className="border-0 shadow-sm">
              <CardHeader className="pb-2"><CardTitle className="text-base">🏆 Öğrenci Sıralaması (XP)</CardTitle></CardHeader>
              <CardContent><div className="space-y-2">
                {[...riskler].sort((a, b) => (b.toplam_xp || 0) - (a.toplam_xp || 0)).map((r, i) => (
                  <div key={r.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-xl cursor-pointer hover:bg-gray-100" onClick={() => ogrenciDetayCek(r)}>
                    <div className="flex items-center gap-2">
                      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold ${i === 0 ? 'bg-yellow-100 text-yellow-700' : i === 1 ? 'bg-gray-100 text-gray-600' : i === 2 ? 'bg-orange-100 text-orange-700' : 'bg-gray-50 text-gray-500'}`}>{i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : i + 1}</div>
                      <div><div className="font-medium text-sm">{r.ad} {r.soyad}</div><div className="text-[10px] text-gray-400">{r.sinif}. sınıf • {r.kur || "—"}</div></div>
                    </div>
                    <div className="flex items-center gap-3 text-xs">
                      <span className={`${r.risk_seviye === "yuksek" ? "text-red-500" : r.risk_seviye === "orta" ? "text-yellow-500" : "text-green-500"}`}>{r.risk_seviye === "yuksek" ? "🔴" : r.risk_seviye === "orta" ? "🟡" : "🟢"}</span>
                      <span className="text-gray-500">🔥{r.streak}</span>
                      <span className="font-bold text-orange-600">{r.toplam_xp || 0} XP</span>
                    </div>
                  </div>
                ))}
              </div></CardContent>
            </Card>
          )}

          {/* Rozetlerim — kompakt, son kazanılanlar + tıkla-aç */}
          {rozetTanimlari.length > 0 && (() => {
            const kazanilanlar = rozetTanimlari.filter(r => rozetlerim.some(k => k.rozet_kodu === r.kod));
            const sonKazanilanlar = kazanilanlar.slice(0, 5);
            return (
              <div className="bg-white rounded-2xl p-4 shadow-sm border">
                <div className="flex items-center justify-between cursor-pointer" onClick={() => setRozetDetayAcik(!rozetDetayAcik)}>
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🏅</span>
                    <span className="font-bold text-sm text-gray-900">Rozetlerim</span>
                    <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{kazanilanlar.length}/{rozetTanimlari.length}</span>
                  </div>
                  <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${rozetDetayAcik ? 'rotate-180' : ''}`} />
                </div>
                {/* Mini önizleme — son 5 rozet */}
                {!rozetDetayAcik && kazanilanlar.length > 0 && (
                  <div className="flex gap-1.5 mt-2">{sonKazanilanlar.map(r => (
                    <span key={r.kod} className="text-xl" title={r.ad}>{r.ikon}</span>
                  ))}{kazanilanlar.length > 5 && <span className="text-xs text-gray-400 self-center">+{kazanilanlar.length - 5}</span>}</div>
                )}
                {/* Detay — tüm rozetler */}
                {rozetDetayAcik && (() => {
                  const rozetKriterleri = {
                    "icerik_ilk": "Gelişim alanına ilk içeriğinizi (hizmetiçi, film, kitap veya makale) ekleyin.",
                    "icerik_5": "Toplam 5 içerik ekleyin ve yayına alınsın.",
                    "icerik_20": "20 farklı içerik ekleyip yayına alarak kütüphaneyi zenginleştirin.",
                    "icerik_50": "50 içerikle platformun en değerli bilgi kaynağı olun.",
                    "oy_ilk": "Gelişim alanındaki herhangi bir içeriği oylayın.",
                    "oy_20": "20 farklı içeriği inceleyip oylayarak kalite kontrolüne katkı sağlayın.",
                    "oy_50": "50 içerik oylamasına katılarak baş editör seviyesine ulaşın.",
                    "gorev_ilk": "Öğrencilerinize ilk görevi atayın.",
                    "gorev_20": "20 görev atayın ve en az 10 tanesi öğrenciler tarafından tamamlansın.",
                    "ilham_veren": "Öğrencilerinizin ortalama okuma streak'i 7+ gün olsun.",
                    "yildiz_egitimci": "Öğrencilerinizin ortalama streak'i 10+ güne ulaşsın.",
                    "kur_ilk": "İlk öğrenciniz kur atlasın — öğretmen onayıyla.",
                    "kur_20": "Toplam 20 kur atlama gerçekleştirin.",
                    "kur_30": "30 kur atlama ile seviye atlatan eğitimci olun.",
                    "kur_50": "50 kur atlama — süper eğitimci statüsü!",
                    "kur_100": "100 kur atlama ile dönüşüm lideri olun.",
                    "veli_ilk": "İlk veli anketinde ortalama 4+ puan alın.",
                    "veli_20": "20 veli anketinde ortalama 4.5+ puan alın.",
                    "veli_30": "30 veli anketinde ort. 4.5+ ve %90 tavsiye oranı yakalayın.",
                    "veli_100": "100 veli anketinde ort. 4.8+ ve %95 tavsiye — efsane öğretmen!",
                    "gelisim_ilk": "İlk gelişim içeriğini tamamlayın (test çözün veya tamamla deyin).",
                    "gelisim_10": "10 gelişim içeriği tamamlayarak sürekli öğrenen olun.",
                    "gelisim_uzman": "30 içerik + %90 test başarısıyla uzman öğretmen seviyesine ulaşın.",
                    "mesaj_ilk": "Öğrencinize veya veliye ilk mesajınızı gönderin.",
                    "kopru_kurucu": "Hem öğrenciye hem veliye mesaj göndererek köprü kurun.",
                    "egz_ilk": "İlk egzersizi tamamlayın — göz jimnastiği ile başlayabilirsiniz.",
                    "egz_tamset": "14 egzersiz türünün tamamını en az birer kez deneyin.",
                  };
                  const seviyeRenk = { bronz: "bg-amber-100 text-amber-700 border-amber-300", gumus: "bg-gray-100 text-gray-700 border-gray-300", altin: "bg-yellow-100 text-yellow-700 border-yellow-300", platin: "bg-cyan-100 text-cyan-700 border-cyan-300", elmas: "bg-purple-100 text-purple-700 border-purple-300" };
                  return (
                    <div className="mt-3 pt-3 border-t border-gray-100">
                      <div className="grid grid-cols-5 sm:grid-cols-7 gap-1.5">
                        {rozetTanimlari.map(r => {
                          const kazandi = rozetlerim.some(k => k.rozet_kodu === r.kod);
                          return (
                            <div key={r.kod} onClick={(e) => { e.stopPropagation(); setSeciliRozet(seciliRozet?.kod === r.kod ? null : {...r, kazandi, kriter: rozetKriterleri[r.kod] || ""}); }}
                              className={`text-center p-1.5 rounded-lg cursor-pointer transition-all hover:scale-105 ${kazandi ? 'bg-orange-50 border border-orange-200' : 'opacity-25 hover:opacity-50'} ${seciliRozet?.kod === r.kod ? 'ring-2 ring-blue-400 scale-105' : ''}`}>
                              <div className="text-lg">{kazandi ? r.ikon : "🔒"}</div>
                              <div className="text-[8px] text-gray-500 truncate">{r.ad}</div>
                            </div>
                          );
                        })}
                      </div>
                      {/* Rozet detay popup */}
                      {seciliRozet && (
                        <div className="mt-3 bg-gradient-to-r from-gray-50 to-white rounded-xl p-4 border border-gray-200 shadow-sm">
                          <div className="flex items-start gap-3">
                            <div className="text-3xl">{seciliRozet.kazandi ? seciliRozet.ikon : "🔒"}</div>
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-sm">{seciliRozet.ad}</span>
                                <span className={`text-[10px] px-1.5 py-0.5 rounded-full border ${seviyeRenk[seciliRozet.seviye] || "bg-gray-100"}`}>{seciliRozet.seviye}</span>
                                <span className="text-xs text-orange-600 font-medium">+{seciliRozet.puan} puan</span>
                              </div>
                              <p className="text-xs text-gray-600 mt-1">{seciliRozet.kriter}</p>
                              <div className="mt-2">{seciliRozet.kazandi
                                ? <span className="text-xs text-green-600 font-medium bg-green-50 px-2 py-1 rounded-full">✅ Kazanıldı!</span>
                                : <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-full">🔒 Henüz kazanılmadı — yukarıdaki kriteri tamamlayın</span>
                              }</div>
                            </div>
                            <button onClick={(e) => { e.stopPropagation(); setSeciliRozet(null); }} className="text-gray-400 hover:text-gray-600 text-sm">✕</button>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}
              </div>
            );
          })()}

          {/* Veli Değerlendirmesi — kompakt, tıkla-aç */}
          {anketOzet && anketOzet.anket_sayisi > 0 && (
            <div className="bg-white rounded-2xl p-4 shadow-sm border">
              <div className="flex items-center justify-between cursor-pointer" onClick={() => setAnketDetayAcik(!anketDetayAcik)}>
                <div className="flex items-center gap-3">
                  <span className="text-lg">💜</span>
                  <span className="font-bold text-sm text-gray-900">Veli Değerlendirmesi</span>
                  <span className="text-lg font-bold text-purple-600">⭐ {anketOzet.ortalama}</span>
                  <span className="text-xs text-green-600 font-medium">%{anketOzet.tavsiye_oran}</span>
                </div>
                <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${anketDetayAcik ? 'rotate-180' : ''}`} />
              </div>
              {/* Detay — kategori grafikleri + ipuçları */}
              {anketDetayAcik && (() => {
                const ipuclari = {
                  iletisim: {
                    baslik: "💬 İletişim",
                    puan: anketOzet.kategoriler?.iletisim,
                    ipuclari: [
                      "Öğrenciyle bire bir kısa görüşmeler yapın — 2 dakika bile fark yaratır",
                      "Velilere haftalık kısa mesaj gönderin: 'Bu hafta Ali şunu başardı...'",
                      "Olumlu geri bildirimle başlayın, gelişim alanlarını sonra nazikçe ekleyin",
                      "Öğrencinin adını kullanarak kişisel hitap edin",
                    ]
                  },
                  duzen: {
                    baslik: "📋 Düzen",
                    puan: anketOzet.kategoriler?.duzen,
                    ipuclari: [
                      "Her hafta aynı gün görev atayın — düzenlilik güven oluşturur",
                      "Görevlere net son tarih koyun ve hatırlatma gönderin",
                      "Haftalık rutininizi velilerle paylaşın — ne zaman ne yapılacak belli olsun",
                      "Okuma takvimi oluşturup öğrenci ve veliye gönderin",
                    ]
                  },
                  etki: {
                    baslik: "📈 Etki",
                    puan: anketOzet.kategoriler?.etki,
                    ipuclari: [
                      "Kur atlama raporlarını velilerle paylaşın — somut ilerleme göstersin",
                      "Okuma süresi grafiğini veliye gösterin: 'İlk ay 5 dk, şimdi 15 dk!'",
                      "Öğrencinin streak geçmişini vurgulayın — tutarlılık velileri etkiler",
                      "Dönem başı vs dönem sonu karşılaştırma yapın",
                    ]
                  },
                  geri_bildirim: {
                    baslik: "📝 Geri Bildirim",
                    puan: anketOzet.kategoriler?.geri_bildirim,
                    ipuclari: [
                      "Test sonuçlarından sonra kısa bir yorum yazın: 'Anlama becerisi gelişiyor'",
                      "Ayda en az 1 kez detaylı geri bildirim mesajı gönderin",
                      "Güçlü yönleri + gelişim alanlarını dengeli verin",
                      "Mesaj sistemini aktif kullanın — veliler yanıt bekliyor",
                    ]
                  },
                  motivasyon: {
                    baslik: "🔥 Motivasyon",
                    puan: anketOzet.kategoriler?.motivasyon,
                    ipuclari: [
                      "Streak tebrik mesajları gönderin: '7 gün! Harika gidiyorsun!'",
                      "Rozet kazanıldığında veliye de bilgi verin",
                      "Kitap bitirme kutlaması yapın — küçük başarılar önemli",
                      "Öğrencinin ilgi alanına uygun kitap önerileri sunun",
                    ]
                  },
                  icerik: {
                    baslik: "📚 İçerik Çeşitliliği",
                    puan: anketOzet.kategoriler?.icerik,
                    ipuclari: [
                      "Farklı türlerde görevler atayın: kitap, film, makale karışık",
                      "Gelişim alanına yeni içerikler ekleyin — çeşitlilik öğrenciyi canlı tutar",
                      "Egzersizleri deneyin ve öğrencilere önerin",
                      "Yaş grubuna uygun güncel kitaplar havuza ekleyin",
                    ]
                  },
                  genel: {
                    baslik: "⭐ Genel Memnuniyet",
                    puan: anketOzet.kategoriler?.genel,
                    ipuclari: [
                      "Tüm kategorilerde tutarlı olun — zayıf alan genel puanı düşürür",
                      "En düşük puanlı kategoriye öncelik verin",
                      "Velilerle dönem başı beklenti görüşmesi yapın",
                      "Küçük ama düzenli iyileştirmeler büyük fark yaratır",
                    ]
                  }
                };
                const katRenk = (v) => v >= 4.5 ? "bg-green-500" : v >= 4.0 ? "bg-purple-500" : v >= 3.5 ? "bg-yellow-500" : "bg-red-500";

                return (
                  <div className="mt-3 pt-3 border-t border-gray-100 space-y-3">
                    <div className="grid grid-cols-3 gap-3">
                      <div className="text-center"><div className="text-2xl font-bold text-purple-600">⭐ {anketOzet.ortalama}</div><div className="text-[10px] text-gray-500">/ 5 ortalama</div></div>
                      <div className="text-center"><div className="text-2xl font-bold text-green-600">%{anketOzet.tavsiye_oran}</div><div className="text-[10px] text-gray-500">tavsiye oranı</div></div>
                      <div className="text-center"><div className="text-2xl font-bold text-blue-600">{anketOzet.anket_sayisi}</div><div className="text-[10px] text-gray-500">anket</div></div>
                    </div>
                    {Object.keys(anketOzet.kategoriler || {}).length > 0 && (
                      <div className="space-y-1">
                        <p className="text-[10px] text-gray-400 mb-1">Kategoriye tıklayarak ipuçları görün →</p>
                        {Object.entries(anketOzet.kategoriler).map(([k, v]) => (
                          <div key={k}>
                            <div className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 rounded-lg px-1 py-0.5 transition-all" onClick={() => setSeciliKategori(seciliKategori === k ? null : k)}>
                              <span className={`text-[10px] w-16 text-right ${seciliKategori === k ? 'font-bold text-purple-700' : 'text-gray-500'}`}>{({"iletisim":"İletişim","duzen":"Düzen","etki":"Etki","geri_bildirim":"Geri Bild.","motivasyon":"Motivasyon","icerik":"İçerik","genel":"Genel"})[k] || k}</span>
                              <div className="flex-1 bg-gray-100 rounded-full h-1.5"><div className={`h-1.5 rounded-full transition-all ${katRenk(v)}`} style={{width:`${v/5*100}%`}} /></div>
                              <span className={`text-[10px] font-medium w-8 ${v >= 4.5 ? 'text-green-600' : v >= 4.0 ? 'text-purple-600' : v >= 3.5 ? 'text-yellow-600' : 'text-red-600'}`}>{v}</span>
                              <ChevronDown className={`h-3 w-3 text-gray-300 transition-transform ${seciliKategori === k ? 'rotate-180' : ''}`} />
                            </div>
                            {seciliKategori === k && ipuclari[k] && (
                              <div className="ml-1 mt-1 mb-2 bg-gradient-to-r from-purple-50 to-white rounded-xl p-3 border border-purple-100">
                                <div className="text-xs font-bold text-purple-700 mb-1.5">{ipuclari[k].baslik} — Puanınızı artırmak için:</div>
                                <div className="space-y-1.5">
                                  {ipuclari[k].ipuclari.map((tip, i) => (
                                    <div key={i} className="flex items-start gap-2">
                                      <span className="text-purple-400 text-xs mt-0.5">💡</span>
                                      <span className="text-xs text-gray-600">{tip}</span>
                                    </div>
                                  ))}
                                </div>
                                {v < 4.5 && <div className="mt-2 text-[10px] text-purple-500 italic">Şu anki puan: {v} → Hedefiniz: 4.5+ ile bu alanda mükemmel seviyeye ulaşın</div>}
                                {v >= 4.5 && <div className="mt-2 text-[10px] text-green-600 italic">🎉 Bu kategoride harika gidiyorsunuz! Tutarlılığı koruyun.</div>}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          )}

          {/* Hızlı eylemler */}
          <div className="grid grid-cols-2 gap-3">
            <button onClick={() => setAktifSekme("ogrencilerim")} className="bg-white rounded-2xl p-4 shadow-sm border text-left hover:shadow-md transition-all">
              <div className="text-lg mb-1">👥</div><div className="text-sm font-bold text-gray-900">Öğrencileri Gör</div><div className="text-[10px] text-gray-500">Detaylı profil ve takip</div>
            </button>
            <button onClick={() => { setAktifSekme("ogrencilerim"); setGorevAtaGoster(true); }} className="bg-white rounded-2xl p-4 shadow-sm border text-left hover:shadow-md transition-all">
              <div className="text-lg mb-1">📌</div><div className="text-sm font-bold text-gray-900">Görev Ata</div><div className="text-[10px] text-gray-500">Toplu veya tekli görev</div>
            </button>
            <button onClick={() => setAktifSekme("giris-analizi")} className="bg-white rounded-2xl p-4 shadow-sm border text-left hover:shadow-md transition-all">
              <div className="text-lg mb-1">🔬</div><div className="text-sm font-bold text-gray-900">Analiz Yap</div><div className="text-[10px] text-gray-500">Giriş analizi başlat</div>
            </button>
            <button onClick={() => setAktifSekme("mesajlar")} className="bg-white rounded-2xl p-4 shadow-sm border text-left hover:shadow-md transition-all">
              <div className="text-lg mb-1">✉️</div><div className="text-sm font-bold text-gray-900">Mesajlar</div><div className="text-[10px] text-gray-500">{okunmamisSayisi > 0 ? `${okunmamisSayisi} okunmamış` : "Tüm mesajlar"}</div>
            </button>
          </div>
          {/* Hedeflerim — kompakt ilerleme kartı */}
          <div className="bg-white rounded-2xl p-4 shadow-sm border">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-lg">🎯</span>
                <span className="font-bold text-sm text-gray-900">Hedeflerim</span>
                {hedefler.length > 0 && <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{hedefler.filter(h => h.tamamlandi).length}/{hedefler.length} tamamlandı</span>}
              </div>
              <button onClick={() => setHedefEkleAcik(!hedefEkleAcik)} className="text-xs text-blue-600 hover:underline">{hedefEkleAcik ? "Kapat" : "+ Hedef Ekle"}</button>
            </div>

            {/* Hedef ekleme formu */}
            {hedefEkleAcik && (() => {
              const sablonlar = [
                {kod:"ogrenci_sayisi", baslik:"Öğrenci Sayısı", ikon:"👥", birim:"öğrenci", ornek:15},
                {kod:"kur_atlama", baslik:"Kur Atlama", ikon:"🎓", birim:"kur atlama", ornek:10},
                {kod:"icerik_uretme", baslik:"İçerik Üretme", ikon:"📚", birim:"içerik", ornek:5},
                {kod:"gorev_atama", baslik:"Görev Tamamlatma", ikon:"📌", birim:"görev", ornek:20},
                {kod:"streak_ortalama", baslik:"Streak Ortalaması", ikon:"🔥", birim:"gün", ornek:7},
                {kod:"veli_puan", baslik:"Veli Puanı", ikon:"⭐", birim:"puan", ornek:4.5},
                {kod:"rozet_sayisi", baslik:"Rozet Kazanma", ikon:"🏅", birim:"rozet", ornek:15},
                {kod:"risk_azaltma", baslik:"Düşük Riskli Öğrenci", ikon:"🛡️", birim:"öğrenci", ornek:10},
              ];
              const seciliSablon = sablonlar.find(s => s.kod === hedefForm.kod);
              return (
                <div className="bg-blue-50 rounded-xl p-3 mb-3 border border-blue-100 space-y-2">
                  <Label className="text-xs font-medium">Hedef Türü</Label>
                  <div className="grid grid-cols-4 gap-1.5">
                    {sablonlar.map(s => (
                      <button key={s.kod} type="button" onClick={() => setHedefForm({...hedefForm, kod: s.kod, hedef_deger: s.ornek})}
                        className={`p-2 rounded-lg text-center transition-all border ${hedefForm.kod === s.kod ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'}`}>
                        <div className="text-lg">{s.ikon}</div>
                        <div className="text-[9px] leading-tight">{s.baslik}</div>
                      </button>
                    ))}
                  </div>
                  {seciliSablon && (<>
                    <div className="grid grid-cols-2 gap-2">
                      <div><Label className="text-[10px]">Hedef Değer</Label><Input type="number" step="0.1" value={hedefForm.hedef_deger} onChange={e => setHedefForm({...hedefForm, hedef_deger: parseFloat(e.target.value) || 0})} className="h-8 text-sm" /></div>
                      <div><Label className="text-[10px]">Son Tarih (opsiyonel)</Label><Input type="date" value={hedefForm.son_tarih} onChange={e => setHedefForm({...hedefForm, son_tarih: e.target.value})} className="h-8 text-sm" /></div>
                    </div>
                    <Button size="sm" className="w-full bg-blue-600 text-white text-xs" onClick={async () => {
                      try {
                        await axios.post(`${API}/hedefler`, { kod: seciliSablon.kod, baslik: seciliSablon.baslik, ikon: seciliSablon.ikon, hedef_deger: hedefForm.hedef_deger, birim: seciliSablon.birim, son_tarih: hedefForm.son_tarih });
                        toast({ title: `🎯 Hedef eklendi: ${seciliSablon.baslik}` });
                        setHedefEkleAcik(false); setHedefForm({ kod: "", hedef_deger: 0, son_tarih: "" });
                        const r = await axios.get(`${API}/hedefler`); setHedefler(Array.isArray(r.data) ? r.data : []);
                      } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
                    }}>🎯 Hedef Belirle</Button>
                  </>)}
                </div>
              );
            })()}

            {/* Hedef listesi */}
            {hedefler.length > 0 ? (
              <div className="space-y-2">
                {hedefler.map(h => (
                  <div key={h.id} className={`rounded-xl p-3 border transition-all ${h.tamamlandi ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-100'}`}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{h.tamamlandi ? "✅" : h.ikon}</span>
                        <div>
                          <span className="text-xs font-medium text-gray-800">{h.baslik}</span>
                          {h.son_tarih && <span className="text-[9px] text-gray-400 ml-1">({h.son_tarih})</span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`text-xs font-bold ${h.tamamlandi ? 'text-green-600' : h.ilerleme >= 75 ? 'text-blue-600' : 'text-gray-600'}`}>{h.mevcut_deger}/{h.hedef_deger}</span>
                        <button onClick={async () => { try { await axios.delete(`${API}/hedefler/${h.id}`); const r = await axios.get(`${API}/hedefler`); setHedefler(Array.isArray(r.data) ? r.data : []); } catch(e) {} }} className="text-gray-300 hover:text-red-400 text-xs">✕</button>
                      </div>
                    </div>
                    <div className="bg-white rounded-full h-1.5 overflow-hidden">
                      <div className={`h-1.5 rounded-full transition-all ${h.tamamlandi ? 'bg-green-500' : h.ilerleme >= 75 ? 'bg-blue-500' : h.ilerleme >= 50 ? 'bg-yellow-500' : 'bg-gray-300'}`} style={{width:`${h.ilerleme}%`}} />
                    </div>
                  </div>
                ))}
              </div>
            ) : !hedefEkleAcik && (
              <div className="text-center py-3">
                <p className="text-xs text-gray-400">Henüz hedef belirlemediniz</p>
                <button onClick={() => setHedefEkleAcik(true)} className="text-xs text-blue-600 mt-1 hover:underline">İlk hedefinizi belirleyin →</button>
              </div>
            )}
          </div>

        </>)}

        {/* ═══ ÖĞRENCİLERİM ═══ */}
        {aktifSekme === "ogrencilerim" && (<>
          {/* Risk özeti */}
          {riskler.length > 0 && (<div className="grid grid-cols-3 gap-3">
            <div className="bg-green-50 rounded-xl p-3 text-center border border-green-100"><div className="text-xl font-bold text-green-700">{riskler.filter(r => r.risk_seviye === "dusuk").length}</div><div className="text-[10px] text-green-600">🟢 Düşük Risk</div></div>
            <div className="bg-yellow-50 rounded-xl p-3 text-center border border-yellow-100"><div className="text-xl font-bold text-yellow-700">{riskler.filter(r => r.risk_seviye === "orta").length}</div><div className="text-[10px] text-yellow-600">🟡 Orta Risk</div></div>
            <div className="bg-red-50 rounded-xl p-3 text-center border border-red-100"><div className="text-xl font-bold text-red-700">{riskler.filter(r => r.risk_seviye === "yuksek").length}</div><div className="text-[10px] text-red-600">🔴 Yüksek Risk</div></div>
          </div>)}

          <div className="flex items-center justify-between"><h2 className="text-lg font-bold">👥 Öğrencilerim</h2>
            <Button size="sm" onClick={() => setGorevAtaGoster(!gorevAtaGoster)} className="bg-orange-500 text-white text-xs"><Plus className="h-3 w-3 mr-1" />Görev Ata</Button></div>

          {/* Hızlı görev atama */}
          {gorevAtaGoster && (<Card className="border-0 shadow-sm border-l-4 border-l-orange-500"><CardContent className="p-4"><form onSubmit={gorevAta} className="space-y-3">
            <div className="text-sm font-medium text-gray-700">Hızlı Görev Ata</div>
            <div className="flex flex-wrap gap-1">{ogrenciler.map(s => (<button key={s.id} type="button" onClick={() => setGorevHedefler(prev => prev.includes(s.id) ? prev.filter(x => x !== s.id) : [...prev, s.id])} className={`px-2 py-1 rounded-lg text-xs border ${gorevHedefler.includes(s.id) ? 'bg-orange-500 text-white border-orange-500' : 'bg-white text-gray-600 border-gray-200'}`}>{s.ad} {s.soyad}</button>))}<button type="button" onClick={() => setGorevHedefler(gorevHedefler.length === ogrenciler.length ? [] : ogrenciler.map(s => s.id))} className="text-xs text-blue-600 px-2">{gorevHedefler.length === ogrenciler.length ? "Kaldır" : "Tümü"}</button></div>
            <div className="grid grid-cols-2 gap-2"><div><Label className="text-xs">Başlık *</Label><Input value={gorevForm.baslik} onChange={e => setGorevForm({...gorevForm, baslik: e.target.value})} required className="text-sm" /></div><div><Label className="text-xs">Son Tarih</Label><Input type="date" value={gorevForm.son_tarih} onChange={e => setGorevForm({...gorevForm, son_tarih: e.target.value})} className="text-sm" /></div></div>
            <div><Label className="text-xs">Açıklama</Label><Input value={gorevForm.aciklama} onChange={e => setGorevForm({...gorevForm, aciklama: e.target.value})} className="text-sm" placeholder="Detay..." /></div>
            <Button type="submit" className="w-full bg-orange-500 text-white text-sm" disabled={gorevHedefler.length === 0}>{gorevHedefler.length > 0 ? `${gorevHedefler.length} Öğrenciye Ata` : "Öğrenci Seçin"}</Button>
          </form></CardContent></Card>)}

          {/* Öğrenci listesi */}
          {(riskler.length > 0 ? riskler : ogrenciler).map(s => {
            const risk = riskler.find(r => r.id === s.id);
            return (<Card key={s.id} className="border-0 shadow-sm cursor-pointer hover:shadow-md transition-all" onClick={() => ogrenciDetayCek(s)}>
              <CardContent className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold ${risk ? riskRenk(risk.risk_seviye) : 'bg-gray-100 text-gray-600'}`}>{risk ? riskIcon(risk.risk_seviye) : "👤"}</div>
                  <div><div className="font-bold text-sm">{s.ad} {s.soyad}</div><div className="text-xs text-gray-500">{s.sinif}. sınıf • {s.kur || "—"}</div></div>
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  {risk && (<><span title="Streak">{risk.streak > 0 ? `🔥${risk.streak}` : "—"}</span><span title="7 gün">{risk.dakika_7}dk/7g</span><span title="XP" className="text-orange-600 font-medium">{risk.toplam_xp} XP</span></>)}
                  <ChevronRight className="h-4 w-4 text-gray-300" />
                </div>
              </CardContent>
            </Card>);
          })}
          {ogrenciler.length === 0 && riskler.length === 0 && (<div className="text-center py-12"><div className="text-5xl mb-3">👥</div><p className="text-gray-500">Henüz öğrenciniz yok</p></div>)}
        </>)}

        {/* ═══ GÖREVLER ═══ */}
        {aktifSekme === "gorevler" && (<div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">📌 Görev Yönetimi</h2>
            <Button size="sm" onClick={() => { setAktifSekme("ogrencilerim"); setGorevAtaGoster(true); }} className="bg-orange-500 text-white text-xs"><Plus className="h-3 w-3 mr-1" />Yeni Görev Ata</Button>
          </div>
          {benimGorevlerim.filter(g => g.durum !== "tamamlandi").length > 0 && (<div className="bg-indigo-50 rounded-xl p-3 border border-indigo-100"><div className="text-sm font-medium text-indigo-700 mb-2">📌 Bana Atanan Görevler</div>{benimGorevlerim.filter(g => g.durum !== "tamamlandi").map(g => (<div key={g.id} className="flex items-center justify-between py-1"><span className="text-sm">{g.baslik}</span><Button size="sm" className="bg-green-600 text-white text-xs h-7" onClick={async () => { try { await axios.put(`${API}/gorevler/${g.id}/durum`, { durum: "tamamlandi" }); toast({ title: "✅ Tamamlandı" }); fetchAll(); } catch(e) {} }}>Tamamla</Button></div>))}</div>)}
          <h3 className="text-sm font-medium text-gray-500">Atadığım Görevler ({atadiklarim.length})</h3>
          {atadiklarim.length === 0 ? <p className="text-center text-gray-400 py-8">Henüz görev atamadınız</p> : atadiklarim.map(g => (
            <div key={g.id} className={`bg-white rounded-xl p-3 shadow-sm border ${g.durum === "tamamlandi" ? "opacity-60" : ""}`}>
              <div className="flex items-center justify-between"><div className="font-medium text-sm">{g.baslik}</div><span className={`text-xs px-2 py-0.5 rounded-full ${g.durum === "tamamlandi" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"}`}>{g.durum === "tamamlandi" ? "✅" : "⏳"}</span></div>
              <div className="text-xs text-gray-400 mt-1">📌 {g.hedef_ad} {g.son_tarih && `• Son: ${new Date(g.son_tarih).toLocaleDateString('tr-TR')}`}</div>
            </div>
          ))}
        </div>)}

        {/* ═══ GİRİŞ ANALİZİ ═══ */}
        {aktifSekme === "giris-analizi" && (<GirisAnaliziModul user={user} students={ogrenciler} teachers={[]} />)}

        {/* ═══ GELİŞİM ═══ */}
        {aktifSekme === "gelisim" && (<GelisimAlani user={user} />)}

        {/* ═══ MESAJLAR ═══ */}
        {aktifSekme === "mesajlar" && (<div className="space-y-4">
          <h2 className="text-lg font-bold">✉️ Mesajlar</h2>
          <div className="flex gap-2">
            {[{v:"gelen",l:`Gelen (${gelenMesajlar.length})`},{v:"giden",l:"Gönderilen"},{v:"yeni",l:"Yeni Mesaj"}].map(t => (
              <button key={t.v} onClick={() => setMesajGorunum(t.v)} className={`px-3 py-1.5 rounded-xl text-xs font-medium border ${mesajGorunum === t.v ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-200'}`}>{t.l}</button>
            ))}
          </div>
          {mesajGorunum === "yeni" && (<Card className="border-0 shadow-sm"><CardContent className="p-4"><form onSubmit={mesajGonder} className="space-y-3">
            <div><Label className="text-xs">Alıcı *</Label><Select value={mesajAlici} onValueChange={setMesajAlici}><SelectTrigger className="text-sm"><SelectValue placeholder="Kişi seçin..." /></SelectTrigger><SelectContent>{kullanicilar.filter(u => u.id !== user.id).map(u => (<SelectItem key={u.id} value={u.id}>{u.ad} {u.soyad} ({({admin:"Yönetici",coordinator:"Koord.",teacher:"Öğretmen",student:"Öğrenci",parent:"Veli"})[u.role]})</SelectItem>))}</SelectContent></Select></div>
            <div><Label className="text-xs">Konu</Label><Input value={mesajForm.konu} onChange={e => setMesajForm({...mesajForm, konu: e.target.value})} className="text-sm" /></div>
            <div><Label className="text-xs">Mesaj *</Label><textarea value={mesajForm.icerik} onChange={e => setMesajForm({...mesajForm, icerik: e.target.value})} required className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[80px]" /></div>
            <Button type="submit" className="w-full bg-blue-600 text-white text-sm">✉️ Gönder</Button>
          </form></CardContent></Card>)}
          {mesajGorunum === "gelen" && (<div className="space-y-2">{gelenMesajlar.length === 0 ? <p className="text-center text-gray-400 py-8">Gelen mesaj yok</p> : gelenMesajlar.map(m => (
            <div key={m.id} className={`bg-white rounded-xl p-3 border ${!m.okundu ? 'border-l-4 border-l-blue-500' : ''}`} onClick={() => !m.okundu && mesajOkundu(m.id)}>
              <div className="flex justify-between"><span className="font-medium text-sm">{m.gonderen_ad}</span><span className="text-xs text-gray-400">{new Date(m.tarih).toLocaleDateString('tr-TR')}</span></div>
              {m.konu && <div className="text-xs font-bold mt-1">{m.konu}</div>}<p className="text-sm text-gray-600 mt-1">{m.icerik}</p>
            </div>))}</div>)}
          {mesajGorunum === "giden" && (<div className="space-y-2">{gidenMesajlar.length === 0 ? <p className="text-center text-gray-400 py-8">Gönderilen mesaj yok</p> : gidenMesajlar.map(m => (
            <div key={m.id} className="bg-white rounded-xl p-3 border"><div className="flex justify-between"><span className="font-medium text-sm">→ {m.alici_ad}</span><span className="text-xs text-gray-400">{new Date(m.tarih).toLocaleDateString('tr-TR')}</span></div>{m.konu && <div className="text-xs font-bold mt-1">{m.konu}</div>}<p className="text-sm text-gray-600 mt-1">{m.icerik}</p></div>))}</div>)}
        </div>)}

      </div>
      <Toaster />
    </div>
  );
}

// ═══════════════════════════════════════════════
// ÖĞRENCİ PANELİ
// ═══════════════════════════════════════════════

function OgrenciPaneli({ user, logout }) {
  const { toast } = useToast();
  const [profil, setProfil] = useState(null);
  const [gorevler, setGorevler] = useState([]);
  const [okumaKayitlari, setOkumaKayitlari] = useState([]);
  const [istatistik, setIstatistik] = useState(null);
  const [siralama, setSiralama] = useState(null);
  const [xpDurum, setXpDurum] = useState(null);
  const [ligSiralama, setLigSiralama] = useState(null);
  const [aktifSekme, setAktifSekme] = useState("ana");
  const [gelisimAltSekme, setGelisimAltSekme] = useState("icerikler"); // icerikler, egzersizler, okumalarim
  const [aktifEkran, setAktifEkran] = useState(null);
  const [okumaBasladi, setOkumaBasladi] = useState(false);
  const [aiMotMesaj, setAiMotMesaj] = useState("");
  // Kelime Evrimi state'leri
  const [kelimeData, setKelimeData] = useState(null);
  const [aktifKelime, setAktifKelime] = useState(null);
  const [cevapGosterim, setCevapGosterim] = useState(false);
  const [oyunData, setOyunData] = useState(null);
  const [okumaSuresi, setOkumaSuresi] = useState(0);
  const [okumaDuraklatildi, setOkumaDuraklatildi] = useState(false);
  const okumaInterval = useRef(null);
  const [agaclar, setAgaclar] = useState([]);
  const [neOkudunForm, setNeOkudunForm] = useState({ kitap_adi: "", bolum: "", baslangic_sayfa: "", bitis_sayfa: "", not_text: "" });
  const [mesajlar, setMesajlar] = useState([]);
  const [mesajForm, setMesajForm] = useState({ konu: "", icerik: "" });
  const [mesajGonderiliyor, setMesajGonderiliyor] = useState(false);
  const [okunmamisSayisi, setOkunmamisSayisi] = useState(0);
  const [egzersizPuanlari, setEgzersizPuanlari] = useState({});
  const [gelisimIcerikleri, setGelisimIcerikleri] = useState([]);
  const [gelisimTamamlananlar, setGelisimTamamlananlar] = useState([]);
  const [ogrenciRozetler, setOgrenciRozetler] = useState([]);
  const [ogrenciRozetTanim, setOgrenciRozetTanim] = useState([]);

  const ogrenciId = user.linked_id || user.id;

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${API}/ogrenci-panel/profil`); setProfil(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/ogrenci-panel/gorevler`); setGorevler(Array.isArray(r.data) ? r.data : []); } catch(e) { setGorevler([]); }
    try { const r = await axios.get(`${API}/reading-logs/${ogrenciId}`); setOkumaKayitlari(Array.isArray(r.data) ? r.data : []); } catch(e) { setOkumaKayitlari([]); }
    try { const r = await axios.get(`${API}/reading-logs/${ogrenciId}/istatistik`); setIstatistik(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/ogrenci-panel/siralama`); setSiralama(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/xp/durum/${ogrenciId}`); setXpDurum(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/xp/lig-siralama`); setLigSiralama(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/mesajlar`); setMesajlar(Array.isArray(r.data) ? r.data : []); } catch(e) { setMesajlar([]); }
    try { const r = await axios.get(`${API}/mesajlar/okunmamis-sayisi`); setOkunmamisSayisi(r.data?.sayi || 0); } catch(e) {}
    try { const r = await axios.get(`${API}/egzersiz/puanlar`); setEgzersizPuanlari(r.data || {}); } catch(e) {}
    try { const r = await axios.get(`${API}/gelisim/icerik`); const d = Array.isArray(r.data) ? r.data : []; setGelisimIcerikleri(d.filter(i => i.durum === "yayinda" && (i.hedef_kitle === "hepsi" || i.hedef_kitle === "ogrenci"))); } catch(e) { setGelisimIcerikleri([]); }
    try { const r = await axios.get(`${API}/gelisim/tamamlama/${user.id}`); setGelisimTamamlananlar(Array.isArray(r.data) ? r.data : []); } catch(e) { setGelisimTamamlananlar([]); }
    try { await axios.post(`${API}/rozetler/kontrol`); } catch(e) {}
    try { const r = await axios.get(`${API}/rozetler/${user.id}`); setOgrenciRozetler(Array.isArray(r.data) ? r.data : []); } catch(e) {}
    try { const r = await axios.get(`${API}/rozetler/tanim`); setOgrenciRozetTanim(r.data?.ogrenci || []); } catch(e) {}
  }, [ogrenciId, user.id]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // AI motivasyon mesajı
  useEffect(() => { const f = async () => { try { const r = await axios.get(`${API}/ai/kocluk/${user.id}/motivasyon`); setAiMotMesaj(r.data.mesaj || ""); } catch(e) {} }; f(); }, [user.id]);
  // Kelime Evrimi verilerini yükle
  useEffect(() => { const f = async () => { try { const r = await axios.get(`${API}/ai/kelime-evrimi/${user.id}`); setKelimeData(r.data); } catch(e) {} }; f(); }, [user.id]);
  // Okuma sayacı
  useEffect(() => {
    if (okumaBasladi && !okumaDuraklatildi) {
      okumaInterval.current = setInterval(() => {
        setOkumaSuresi(prev => { const y = prev + 1; if (y % 60 === 0) setAgaclar(a => [...a, { id: Date.now(), buyume: 0 }]); return y; });
      }, 1000);
    } else { clearInterval(okumaInterval.current); }
    return () => clearInterval(okumaInterval.current);
  }, [okumaBasladi, okumaDuraklatildi]);

  useEffect(() => {
    if (agaclar.length > 0) { const t = setInterval(() => { setAgaclar(prev => prev.map(a => a.buyume < 100 ? { ...a, buyume: Math.min(a.buyume + 2, 100) } : a)); }, 100); return () => clearInterval(t); }
  }, [agaclar.length]);

  const dakikaStr = (sn) => `${Math.floor(sn/60).toString().padStart(2,'0')}:${(sn%60).toString().padStart(2,'0')}`;
  const agacEmoji = (b) => b < 30 ? "🌱" : b < 70 ? "🌿" : "🌳";
  const okumaBaslat = () => { setOkumaBasladi(true); setOkumaDuraklatildi(false); setOkumaSuresi(0); setAgaclar([]); setAktifEkran("okuma"); };
  const okumaBitir = () => { clearInterval(okumaInterval.current); setOkumaBasladi(false); setNeOkudunForm({ kitap_adi:"", bolum:"", baslangic_sayfa:"", bitis_sayfa:"", not_text:"" }); setAktifEkran("ne-okudun"); };

  // Socratic Reading state
  const [socraticSoru, setSocraticSoru] = useState(null);
  const [socraticCevap, setSocraticCevap] = useState("");
  const [socraticSonuc, setSocraticSonuc] = useState(null);

  const okumaKaydet = async (e) => {
    e.preventDefault();
    const dk = Math.max(1, Math.round(okumaSuresi / 60));
    try {
      await axios.post(`${API}/reading-logs`, { ...neOkudunForm, baslangic_sayfa: neOkudunForm.baslangic_sayfa ? parseInt(neOkudunForm.baslangic_sayfa) : null, bitis_sayfa: neOkudunForm.bitis_sayfa ? parseInt(neOkudunForm.bitis_sayfa) : null, sure_dakika: dk });
      toast({ title: `🌳 ${dk} dakika okuma kaydedildi!` }); setOkumaSuresi(0); setAgaclar([]);
      // Otomatik XP kazan
      try { await axios.post(`${API}/xp/kazan`, { eylem: "okuma_gorevi" }); } catch(e) {}
      // Socratic soru al
      try {
        const sr = await axios.post(`${API}/ai/socratic-soru`, { kitap_adi: neOkudunForm.kitap_adi, bolum: neOkudunForm.bolum, sure_dk: dk, sinif: user.sinif || 3 });
        setSocraticSoru(sr.data); setSocraticCevap(""); setSocraticSonuc(null);
      } catch(e) { setAktifEkran(null); }
      fetchAll();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const gorevTamamla = async (id) => { try { await axios.put(`${API}/gorevler/${id}/durum`, { durum: "tamamlandi" }); toast({ title: "✅ Görev tamamlandı!" }); try { await axios.post(`${API}/xp/kazan`, { eylem: "gorev_tamamla" }); } catch(e) {} fetchAll(); } catch(e) { toast({ title: "Hata", variant: "destructive" }); } };
  const gelisimTamamla = async (id) => { try { const r = await axios.post(`${API}/gelisim/tamamla`, { icerik_id: id, kullanici_id: user.id }); toast({ title: `+${r.data.puan} puan kazandın!` }); try { await axios.post(`${API}/xp/kazan`, { eylem: "gelisim_tamamla" }); } catch(e) {} fetchAll(); } catch(e) { toast({ title: e.response?.data?.detail || "Hata", variant: "destructive" }); } };

  const mesajGonder = async (e) => {
    e.preventDefault();
    if (!profil?.ogretmen_bilgi) { toast({ title: "Öğretmen bulunamadı", variant: "destructive" }); return; }
    setMesajGonderiliyor(true);
    try {
      const usersRes = await axios.get(`${API}/auth/users`);
      const ogretmenUser = usersRes.data.find(u => u.linked_id === profil.ogretmen_id || u.id === profil.ogretmen_id);
      await axios.post(`${API}/mesajlar`, { alici_id: ogretmenUser ? ogretmenUser.id : profil.ogretmen_id, konu: mesajForm.konu, icerik: mesajForm.icerik });
      toast({ title: "✉️ Mesaj gönderildi!" }); setMesajForm({ konu: "", icerik: "" }); fetchAll();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
    setMesajGonderiliyor(false);
  };
  const mesajOkundu = async (id) => { try { await axios.put(`${API}/mesajlar/${id}/okundu`); fetchAll(); } catch(e) {} };

  const bekleyenGorevler = gorevler.filter(g => g.durum !== "tamamlandi");
  const tamamlananGorevler = gorevler.filter(g => g.durum === "tamamlandi");
  const isTamamlandi = (id) => gelisimTamamlananlar.some(t => t.icerik_id === id);

  // Motivasyon hesaplamaları
  const toplamOkumaSaati = istatistik ? Math.round(istatistik.toplam_dakika / 60) : 0;
  const okunanSayfa = okumaKayitlari.reduce((t, k) => t + (k.bitis_sayfa && k.baslangic_sayfa ? k.bitis_sayfa - k.baslangic_sayfa : 0), 0);
  const tamamlananGorevSayisi = tamamlananGorevler.length;
  const tamamlananGelisim = gelisimTamamlananlar.length;

  // Seviye hesapla (her 100 dakika = 1 seviye)
  const seviye = istatistik ? Math.floor(istatistik.toplam_dakika / 100) + 1 : 1;
  const seviyeIlerleme = istatistik ? (istatistik.toplam_dakika % 100) : 0;
  const seviyeEmoji = seviye <= 2 ? "🌱" : seviye <= 5 ? "🌿" : seviye <= 10 ? "🌳" : seviye <= 20 ? "🏆" : "👑";

  // ── OKUMA RİTÜELİ ──
  if (aktifEkran === "okuma") {
    return (
      <div className="min-h-screen bg-gradient-to-b from-green-50 to-emerald-100 flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full text-center space-y-8">
          <div className="text-lg text-green-800 font-medium">Fiziksel kitabını aç ve oku 📖</div>
          <div className="min-h-[120px] flex items-end justify-center gap-1 flex-wrap p-4 bg-white/50 rounded-3xl">
            {agaclar.length === 0 && <div className="text-4xl opacity-30">🌱</div>}
            {agaclar.map(a => (<span key={a.id} className="text-3xl transition-all duration-500" style={{ transform: `scale(${0.5+a.buyume/200})`, opacity: 0.5+a.buyume/200 }}>{agacEmoji(a.buyume)}</span>))}
          </div>
          <div className="text-xs text-green-600">Her dakika ormanda bir ağaç büyür</div>
          <div className="text-6xl font-mono font-bold text-green-900">{dakikaStr(okumaSuresi)}</div>
          <div className="flex gap-4 justify-center">
            <Button onClick={() => setOkumaDuraklatildi(!okumaDuraklatildi)} variant="outline" className="rounded-full px-8 py-3 text-lg border-green-300 text-green-700">{okumaDuraklatildi ? "▶ Devam Et" : "⏸ Duraklat"}</Button>
            <Button onClick={okumaBitir} className="rounded-full px-8 py-3 text-lg bg-gradient-to-r from-green-500 to-emerald-600 text-white" disabled={okumaSuresi < 30}>✅ Bitirdim</Button>
          </div>
          {okumaSuresi < 30 && <p className="text-xs text-gray-400">En az 30 saniye okuman gerekiyor</p>}
        </div>
      </div>
    );
  }

  // ── NE OKUDUN? ──
  if (aktifEkran === "ne-okudun") {
    const dk = Math.max(1, Math.round(okumaSuresi / 60));
    return (
      <div className="min-h-screen bg-gradient-to-b from-orange-50 to-yellow-50 flex items-center justify-center p-4">
        <div className="max-w-md w-full"><Card className="border-0 shadow-lg"><CardHeader className="text-center"><div className="text-4xl mb-2">🌳🌳🌳</div><CardTitle>Harika! {dk} dakika okudun.</CardTitle><p className="text-gray-500 text-sm">Bugün ne okudun?</p></CardHeader>
          <CardContent><form onSubmit={okumaKaydet} className="space-y-4">
            <div><Label>Kitap Adı *</Label><Input value={neOkudunForm.kitap_adi} onChange={e => setNeOkudunForm({...neOkudunForm, kitap_adi: e.target.value})} required placeholder="Kitabın adı" /></div>
            <div><Label>Bölüm</Label><Input value={neOkudunForm.bolum} onChange={e => setNeOkudunForm({...neOkudunForm, bolum: e.target.value})} placeholder="Bölüm 3" /></div>
            <div className="grid grid-cols-2 gap-3"><div><Label>Başlangıç Sayfa</Label><Input type="number" value={neOkudunForm.baslangic_sayfa} onChange={e => setNeOkudunForm({...neOkudunForm, baslangic_sayfa: e.target.value})} /></div><div><Label>Bitiş Sayfa</Label><Input type="number" value={neOkudunForm.bitis_sayfa} onChange={e => setNeOkudunForm({...neOkudunForm, bitis_sayfa: e.target.value})} /></div></div>
            <div><Label>Not</Label><Input value={neOkudunForm.not_text} onChange={e => setNeOkudunForm({...neOkudunForm, not_text: e.target.value})} placeholder="Kısa not..." /></div>
            <Button type="submit" className="w-full bg-gradient-to-r from-orange-500 to-red-500 text-white py-3 rounded-xl">Kaydet 📝</Button>
            <Button type="button" variant="outline" className="w-full" onClick={() => { setOkumaSuresi(0); setAktifEkran(null); setSocraticSoru(null); }}>Atla</Button>
          </form></CardContent></Card>

          {/* Socratic Reading Popup */}
          {socraticSoru && (
            <Card className="border-2 border-cyan-300 shadow-lg">
              <CardHeader className="bg-gradient-to-r from-cyan-50 to-blue-50 pb-2">
                <CardTitle className="text-base flex items-center gap-2">🤖 Okuma Koçun Soruyor</CardTitle>
              </CardHeader>
              <CardContent className="pt-3 space-y-3">
                <p className="text-sm font-medium text-gray-800">{socraticSoru.soru}</p>
                {socraticSoru.ipucu && <p className="text-xs text-cyan-600 italic">💡 İpucu: {socraticSoru.ipucu}</p>}
                {!socraticSonuc ? (<>
                  <textarea value={socraticCevap} onChange={e => setSocraticCevap(e.target.value)} className="w-full border rounded-lg p-2 text-sm min-h-[60px]" placeholder="Düşünceni yaz..." />
                  <div className="flex gap-2">
                    <Button className="flex-1 bg-cyan-600 text-white text-sm" onClick={async () => {
                      try {
                        const r = await axios.post(`${API}/ai/socratic-cevap`, { soru: socraticSoru.soru, cevap: socraticCevap });
                        setSocraticSonuc(r.data);
                      } catch(e) { setSocraticSonuc({ puan: 3, geri_bildirim: "Teşekkürler! 👏", xp: 5 }); }
                    }}>Gönder 🚀</Button>
                    <Button variant="outline" className="text-sm" onClick={() => { setSocraticSoru(null); setAktifEkran(null); }}>Atla</Button>
                  </div>
                </>) : (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      {[1,2,3,4,5].map(s => <span key={s} className={`text-lg ${s <= socraticSonuc.puan ? '⭐' : '☆'}`}>{s <= socraticSonuc.puan ? '⭐' : '☆'}</span>)}
                      <span className="text-xs text-green-600 font-bold">+{socraticSonuc.xp} XP</span>
                    </div>
                    <p className="text-sm text-gray-700 bg-cyan-50 p-2 rounded-lg">{socraticSonuc.geri_bildirim}</p>
                    <Button className="w-full bg-green-600 text-white text-sm" onClick={() => { setSocraticSoru(null); setSocraticSonuc(null); setAktifEkran(null); }}>Tamam ✅</Button>
                  </div>
                )}
              </CardContent>
            </Card>
          )}</div>
      </div>
    );
  }

  // ── ANA PANEL — Sadeleştirilmiş 4 Tab ──
  const sekmeler = [
    { id: "ana", label: "Ana Sayfa", icon: "🏠" },
    { id: "gorevler", label: "Görevlerim", icon: "📌", badge: bekleyenGorevler.length || null },
    { id: "gelisim", label: "Gelişim", icon: "🎯" },
    { id: "siralama", label: "Sıralama", icon: "🏆" },
    { id: "mesajlar", label: "Mesajlar", icon: "✉️", badge: okunmamisSayisi || null },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-orange-400 to-red-500 rounded-xl flex items-center justify-center"><BookOpen className="h-5 w-5 text-white" /></div>
            <div><div className="font-bold text-gray-900 text-sm">{user.ad} {user.soyad}</div><div className="text-xs text-gray-500">{profil?.kur ? `Kur: ${profil.kur}` : "Öğrenci"} {profil?.sinif ? `• ${profil.sinif}. sınıf` : ""}</div></div>
          </div>
          <div className="flex items-center gap-2">
            <div className="text-center"><div className="text-lg font-bold text-orange-600">{seviyeEmoji} Sv.{seviye}</div></div>
            <BildirimZili user={user} />
            <Button variant="outline" size="sm" onClick={logout} className="text-xs"><LogOut className="h-3 w-3 mr-1" />Çıkış</Button>
          </div>
        </div>
      </div>

      {/* 5 Tab — temiz, taşmaz */}
      <div className="bg-white border-b sticky top-[60px] z-10">
        <div className="max-w-2xl mx-auto px-2 flex justify-between py-2">
          {sekmeler.map(s => (
            <button key={s.id} onClick={() => setAktifSekme(s.id)}
              className={`flex flex-col items-center gap-0.5 px-2 py-1.5 rounded-xl text-[11px] font-medium transition-all min-w-0 flex-1 ${aktifSekme === s.id ? 'bg-orange-500 text-white shadow' : 'text-gray-500 hover:bg-gray-100'}`}>
              <span className="text-base">{s.icon}</span>
              <span className="truncate">{s.label}</span>
              {s.badge > 0 && <span className={`px-1.5 rounded-full text-[9px] font-bold ${aktifSekme === s.id ? 'bg-white/30' : 'bg-red-100 text-red-600'}`}>{s.badge}</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-2xl mx-auto p-4 space-y-4">

        {/* ═══ ANA SAYFA ═══ */}
        {aktifSekme === "ana" && (<>
          {/* Lig Durumu (XP yalnızca sıralama ekranında görünür) */}
          {xpDurum && (
            <div className="bg-gradient-to-r from-orange-500 to-red-500 rounded-2xl p-4 text-white">
              <div className="flex items-center justify-between mb-2">
                <div className="text-lg font-bold">{xpDurum.lig_label}</div>
              </div>
              {xpDurum.sonraki_lig && (<>
                <div className="bg-white/20 rounded-full h-2.5 overflow-hidden"><div className="h-full bg-white rounded-full transition-all" style={{ width: `${Math.min(100, ((xpDurum.toplam_xp - (LIG_ESIKLERI_FE[xpDurum.lig] || 0)) / Math.max(1, xpDurum.sonraki_esik - (LIG_ESIKLERI_FE[xpDurum.lig] || 0))) * 100)}%` }} /></div>
                <p className="text-xs opacity-70 mt-1">Sonraki lig: {({"gumus":"🥈 Gümüş","altin":"🥇 Altın","elmas":"💎 Elmas"})[xpDurum.sonraki_lig]}</p>
              </>)}
              {!xpDurum.sonraki_lig && <p className="text-xs opacity-80 mt-1">En yüksek lige ulaştın! 🎉</p>}
            </div>
          )}
          {!xpDurum && (
            <div className="bg-gradient-to-r from-orange-500 to-red-500 rounded-2xl p-4 text-white">
              <div className="text-lg font-bold">{seviyeEmoji} Seviye {seviye}</div>
              <div className="bg-white/20 rounded-full h-2.5 overflow-hidden mt-2"><div className="h-full bg-white rounded-full" style={{ width: `${seviyeIlerleme}%` }} /></div>
              <p className="text-xs opacity-70 mt-1">Sonraki seviye için {100 - seviyeIlerleme} dk oku</p>
            </div>
          )}

          {/* 2x3 istatistik grid */}
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-orange-600">{istatistik?.streak || 0}</div><div className="text-[10px] text-gray-500">🔥 Gün Streak</div></div>
            <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-green-600">{istatistik?.bugun_dakika || 0}</div><div className="text-[10px] text-gray-500">⏱ Bugün (dk)</div></div>
            <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-blue-600">{istatistik?.toplam_kitap || 0}</div><div className="text-[10px] text-gray-500">📚 Kitap</div></div>
            <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-purple-600">{toplamOkumaSaati}</div><div className="text-[10px] text-gray-500">⏳ Saat Okuma</div></div>
            <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-pink-600">{okunanSayfa}</div><div className="text-[10px] text-gray-500">📄 Sayfa</div></div>
            <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-teal-600">{tamamlananGorevSayisi + tamamlananGelisim}</div><div className="text-[10px] text-gray-500">✅ Tamamlanan</div></div>
          </div>

          {/* 🤖 AI Günlük Motivasyon Mesajı */}
          {aiMotMesaj && (
              <div className="bg-gradient-to-r from-cyan-50 to-blue-50 rounded-2xl p-4 border border-cyan-200 relative">
                <div className="flex items-start gap-3">
                  <div className="text-2xl">🤖</div>
                  <div className="flex-1"><div className="text-xs font-medium text-cyan-700 mb-1">AI Koçun Diyor ki:</div><p className="text-sm text-gray-700">{aiMotMesaj}</p></div>
                </div>
              </div>
          )}

          {/* Haftalık hedef */}
          {istatistik && (<div className="bg-white rounded-2xl p-4 shadow-sm border"><div className="flex items-center justify-between mb-2"><div className="text-sm font-medium text-gray-700">Haftalık Hedef</div><span className="text-sm font-bold text-gray-700">{istatistik.aktif_gunler_7}/4 gün</span></div><div className="flex gap-1">{[0,1,2,3].map(i => (<div key={i} className={`flex-1 h-3 rounded-full ${i < istatistik.aktif_gunler_7 ? 'bg-gradient-to-r from-orange-400 to-red-500' : 'bg-gray-100'}`} />))}</div><p className="text-xs text-gray-400 mt-2">Haftada en az 4 gün okuma 📖</p></div>)}

          {/* Okumaya Başla */}
          <button onClick={okumaBaslat} className="w-full bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-2xl p-5 shadow-lg hover:shadow-xl transition-all active:scale-[0.98]">
            <div className="text-3xl mb-1">🌳</div><div className="text-lg font-bold">Okumaya Başla</div><div className="text-xs opacity-80">Konsantrasyon Ormanını büyüt</div>
          </button>

          {/* Bekleyen görevler kısa */}
          {bekleyenGorevler.length > 0 && (<div className="bg-white rounded-2xl p-4 shadow-sm border">
            <div className="flex items-center justify-between mb-3"><h3 className="font-bold text-sm text-gray-900">📌 Görevlerin</h3><button onClick={() => setAktifSekme("gorevler")} className="text-xs text-blue-600">Tümü →</button></div>
            <div className="space-y-2">{bekleyenGorevler.slice(0,3).map(g => (<div key={g.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-xl"><div className="text-sm font-medium truncate flex-1 mr-2">{g.baslik}</div><Button size="sm" className="bg-green-600 text-white text-[10px] px-2 h-7" onClick={() => gorevTamamla(g.id)}>Tamamla</Button></div>))}</div>
          </div>)}

          {/* Sıralama + Öğretmen yan yana */}
          <div className="grid grid-cols-2 gap-3">
            {(ligSiralama || siralama) && (<div className="bg-gradient-to-br from-yellow-50 to-orange-50 rounded-2xl p-4 border border-yellow-100 cursor-pointer" onClick={() => setAktifSekme("siralama")}>
              <div className="text-xs font-medium text-yellow-800">🏆 Sıralaman</div>
              <div className="text-3xl font-bold text-orange-600 mt-1">{ligSiralama?.benim_siram || siralama?.benim_siram || "—"}.</div>
              <div className="text-[10px] text-gray-500">{ligSiralama?.toplam || siralama?.toplam_ogrenci || 0} öğrenci</div>
            </div>)}
            {profil?.ogretmen_bilgi && (<div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-2xl p-4 border border-blue-100 cursor-pointer" onClick={() => setAktifSekme("mesajlar")}>
              <div className="text-xs font-medium text-blue-800">👩‍🏫 Öğretmenin</div>
              <div className="font-bold text-gray-900 text-sm mt-1">{profil.ogretmen_bilgi.ad} {profil.ogretmen_bilgi.soyad}</div>
              <div className="text-[10px] text-blue-600 mt-1">✉️ Mesaj gönder</div>
            </div>)}
          </div>

          {/* Rozetlerim */}
          {ogrenciRozetTanim.length > 0 && (
            <div className="bg-white rounded-2xl p-4 shadow-sm border">
              <div className="flex items-center justify-between mb-3"><h3 className="font-bold text-sm text-gray-900">🏅 Rozetlerim</h3><span className="text-xs text-gray-500">{ogrenciRozetler.length} / {ogrenciRozetTanim.length}</span></div>
              <div className="grid grid-cols-5 gap-2">
                {ogrenciRozetTanim.slice(0, 15).map(r => {
                  const kazandi = ogrenciRozetler.some(k => k.rozet_kodu === r.kod);
                  return (<div key={r.kod} className={`text-center p-1.5 rounded-xl border ${kazandi ? 'bg-white border-orange-200 shadow-sm' : 'bg-gray-50 border-gray-100 opacity-30'}`} title={r.ad}><div className="text-xl">{kazandi ? r.ikon : "🔒"}</div><div className="text-[8px] text-gray-500 mt-0.5 truncate">{r.ad}</div></div>);
                })}
              </div>
            </div>
          )}

          {/* Son 3 okuma */}
          {okumaKayitlari.length > 0 && (<div className="bg-white rounded-2xl p-4 shadow-sm border">
            <div className="flex items-center justify-between mb-2"><h3 className="font-bold text-sm text-gray-900">📖 Son Okumalar</h3><button onClick={() => { setAktifSekme("gelisim"); setGelisimAltSekme("okumalarim"); }} className="text-xs text-blue-600">Tümü →</button></div>
            {okumaKayitlari.slice(0,3).map(k => (<div key={k.id} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0"><div className="text-sm font-medium truncate flex-1">{k.kitap_adi || "—"}</div><div className="text-xs text-gray-400">{k.sure_dakika} dk</div></div>))}
          </div>)}
        </>)}

        {/* ═══ GÖREVLERİM ═══ */}
        {aktifSekme === "gorevler" && (<div className="space-y-3"><h2 className="text-lg font-bold">📌 Görevlerim</h2>
          {bekleyenGorevler.length === 0 && tamamlananGorevler.length === 0 ? (<div className="text-center py-12"><div className="text-5xl mb-3">✅</div><p className="text-gray-500">Tüm görevler tamamlandı!</p></div>) : (<>
            {bekleyenGorevler.map(g => (<Card key={g.id} className="border-0 shadow-sm"><CardContent className="p-4 flex items-start justify-between gap-3"><div className="min-w-0"><div className="font-bold text-sm">{g.baslik}</div>{g.aciklama && <p className="text-xs text-gray-500 mt-1">{g.aciklama}</p>}<div className="text-xs text-gray-400 mt-1">{g.atayan_ad && `Atayan: ${g.atayan_ad}`}{g.son_tarih && ` • Son: ${new Date(g.son_tarih).toLocaleDateString('tr-TR')}`}</div>{g.film_link && <a href={g.film_link} target="_blank" rel="noreferrer" className="text-xs text-blue-600 block mt-1">🎬 Film Linki</a>}{g.makale_link && <a href={g.makale_link} target="_blank" rel="noreferrer" className="text-xs text-blue-600 block mt-1">📄 Makale</a>}</div><Button size="sm" className="bg-green-600 text-white text-xs shrink-0" onClick={() => gorevTamamla(g.id)}>Tamamla</Button></CardContent></Card>))}
            {tamamlananGorevler.length > 0 && (<><h3 className="text-xs font-medium text-gray-400 mt-4">Tamamlanan ({tamamlananGorevler.length})</h3>{tamamlananGorevler.slice(0,5).map(g => (<div key={g.id} className="bg-green-50 rounded-xl p-3 border border-green-100 opacity-60 text-sm">✅ {g.baslik}</div>))}</>)}
          </>)}
        </div>)}

        {/* ═══ GELİŞİM (İçerikler + Egzersizler + Okumalarım alt sekmeli) ═══ */}
        {aktifSekme === "gelisim" && (<div className="space-y-4">
          <h2 className="text-lg font-bold">🎯 Gelişim</h2>
          {/* Alt sekmeler */}
          <div className="flex gap-2 bg-gray-100 p-1 rounded-xl">
            {[{id:"icerikler",l:"📚 İçerikler"},{id:"egzersizler",l:"👁️ Egzersizler"},{id:"okumalarim",l:"📖 Okumalarım"},{id:"kelime_evrimi",l:"🧠 Kelimelerim"}].map(s => (
              <button key={s.id} onClick={() => setGelisimAltSekme(s.id)}
                className={`flex-1 py-2 rounded-lg text-xs font-medium transition-all ${gelisimAltSekme === s.id ? 'bg-white shadow text-gray-900' : 'text-gray-500'}`}>{s.l}</button>
            ))}
          </div>

          {/* İçerikler */}
          {gelisimAltSekme === "icerikler" && (<>
            {gelisimIcerikleri.length === 0 ? (<div className="text-center py-8"><p className="text-gray-500 text-sm">Henüz içerik yok</p></div>) : (
              gelisimIcerikleri.map(ic => { const done = isTamamlandi(ic.id); return (
                <Card key={ic.id} className={`border-0 shadow-sm ${done ? 'opacity-60' : ''}`}><CardContent className="p-4"><div className="flex items-start justify-between gap-3"><div>
                  <div className="flex items-center gap-2"><span className="text-lg">{({hizmetici:"🎓",film:"🎬",kitap:"📚",makale:"📄"})[ic.tur] || "📋"}</span><div className="font-bold text-sm">{ic.baslik}</div></div>
                  {ic.aciklama && <p className="text-xs text-gray-500 mt-1">{ic.aciklama}</p>}
                </div>{done ? <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">✅</span> : <Button size="sm" className="bg-orange-500 text-white text-xs" onClick={() => gelisimTamamla(ic.id)}>Tamamla</Button>}</div></CardContent></Card>
              ); })
            )}
          </>)}

          {/* Egzersizler */}
          {gelisimAltSekme === "egzersizler" && (
            <EgzersizlerModul user={user} egzersizPuanlari={egzersizPuanlari} onTamamla={async (egzersizId) => {
              try { const r = await axios.post(`${API}/egzersiz/tamamla`, { kullanici_id: user.id, egzersiz_id: egzersizId }); toast({ title: `🎉 +${r.data.kazanilan_puan} puan kazandın!` }); fetchAll(); }
              catch(e) { if (e.response?.status === 409) toast({ title: "Bu egzersizi bugün zaten yaptın" }); else toast({ title: "Hata", variant: "destructive" }); }
            }} />
          )}

          {/* Okumalarım */}
          {gelisimAltSekme === "okumalarim" && (<>
            {okumaKayitlari.length === 0 ? (<div className="text-center py-8"><p className="text-gray-500 text-sm">Henüz okuma kaydı yok</p><Button onClick={okumaBaslat} className="mt-3 bg-green-600 text-white text-sm">🌳 Okumaya Başla</Button></div>) : (
              okumaKayitlari.map(k => (<Card key={k.id} className="border-0 shadow-sm"><CardContent className="p-3 flex items-center justify-between"><div><div className="font-medium text-sm">{k.kitap_adi || "—"}</div><div className="text-xs text-gray-400">{k.bolum && `${k.bolum} • `}⏱ {k.sure_dakika} dk {k.baslangic_sayfa && k.bitis_sayfa && `• s.${k.baslangic_sayfa}-${k.bitis_sayfa}`}</div>{k.not_text && <p className="text-[10px] text-blue-600 mt-0.5">💬 {k.not_text}</p>}</div><div className="text-[10px] text-gray-400">{new Date(k.tarih).toLocaleDateString('tr-TR')}</div></CardContent></Card>))
            )}
          </>)}

          {/* ── Kelime Evrimi (Spaced Repetition) ── */}
          {gelisimAltSekme === "kelime_evrimi" && (() => {
            return (<div className="space-y-3">
              {kelimeData && (
                <div className="grid grid-cols-3 gap-2">
                  <div className="bg-cyan-50 rounded-xl p-3 text-center border border-cyan-200"><div className="text-2xl font-bold text-cyan-600">{kelimeData.bugun_tekrar}</div><div className="text-[9px] text-cyan-700">📝 Bugün Tekrar</div></div>
                  <div className="bg-green-50 rounded-xl p-3 text-center border border-green-200"><div className="text-2xl font-bold text-green-600">{kelimeData.ogrenilmis}</div><div className="text-[9px] text-green-700">✅ Öğrenilmiş</div></div>
                  <div className="bg-purple-50 rounded-xl p-3 text-center border border-purple-200"><div className="text-2xl font-bold text-purple-600">{kelimeData.toplam}</div><div className="text-[9px] text-purple-700">📚 Toplam</div></div>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2">
                {[["eslestirme","🎲 Eşleştirme"],["bosluk_doldurma","⬜ Boşluk Doldur"],["cumle_kurma","📝 Cümle Kur"],["kelime_avi","🔍 Kelime Avı"]].map(([t,l]) => (
                  <button key={t} onClick={async () => {
                    try { const r = await axios.post(`${API}/ai/mini-oyun`, { tur: t, sinif: user.sinif || 3 }); setOyunData(r.data.oyun); } catch(e) {}
                  }} className="bg-white rounded-xl p-3 border shadow-sm text-center hover:bg-gray-50 transition-all">
                    <div className="text-lg">{l.split(" ")[0]}</div><div className="text-[10px] text-gray-600">{l.split(" ").slice(1).join(" ")}</div>
                  </button>
                ))}
              </div>

              {oyunData && (
                <div className="bg-white rounded-xl p-4 border-2 border-cyan-300 shadow-md">
                  <div className="flex items-center justify-between mb-3"><h3 className="font-bold text-sm">{oyunData.baslik}</h3><button onClick={() => setOyunData(null)} className="text-xs text-gray-400">✕</button></div>
                  <p className="text-xs text-gray-600 mb-3">{oyunData.aciklama}</p>
                  {oyunData.tur === "eslestirme" && oyunData.kelimeler && (<div className="space-y-1.5">{oyunData.kelimeler.map((k, i) => (<div key={i} className="flex items-center gap-2 bg-gray-50 rounded-lg p-2"><span className="bg-cyan-100 text-cyan-700 px-2 py-0.5 rounded text-xs font-bold min-w-[80px] text-center">{k}</span><span className="text-xs">↔</span><span className="text-xs text-gray-600">{oyunData.anlamlar?.[i] || ""}</span></div>))}</div>)}
                  {oyunData.tur === "bosluk_doldurma" && oyunData.sorular && (<div className="space-y-2">{oyunData.sorular.map((s, i) => (<div key={i} className="bg-gray-50 rounded-lg p-2"><p className="text-xs mb-1">{s.cumle_bos}</p><div className="flex gap-1 flex-wrap">{(s.secenekler||[]).map((sec, j) => (<button key={j} className="text-[10px] px-2 py-1 rounded bg-white border hover:bg-cyan-50">{sec}</button>))}</div></div>))}</div>)}
                  {oyunData.tur === "kelime_avi" && oyunData.kelimeler && (<div><p className="text-xs text-gray-500 mb-1">Bul: {oyunData.kelimeler.join(", ")}</p></div>)}
                  {oyunData.tur === "cumle_kurma" && oyunData.sorular && (<div className="space-y-2">{oyunData.sorular.map((s, i) => (<div key={i} className="bg-gray-50 rounded-lg p-2"><p className="text-[10px] text-gray-400 mb-1">Hedef: {s.hedef_kelime}</p><div className="flex gap-1 flex-wrap">{(s.karisik||[]).map((k, j) => (<span key={j} className="text-[10px] bg-white border px-2 py-0.5 rounded">{k}</span>))}</div></div>))}</div>)}
                  <Button className="w-full mt-3 bg-green-600 text-white text-sm" onClick={async () => { try { const r = await axios.post(`${API}/ai/mini-oyun/tamamla`, { tur: oyunData.tur, dogru: 5, toplam: 6 }); toast({ title: `🎮 ${r.data.mesaj} +${r.data.xp} XP` }); setOyunData(null); } catch(e) {} }}>Oyunu Tamamla ✅</Button>
                </div>
              )}

              {kelimeData?.bekleyenler?.length > 0 && !oyunData && (<>
                <h3 className="font-bold text-sm text-gray-700">📝 Bugün Tekrar Edilecek Kelimeler</h3>
                {!aktifKelime ? (
                  <button onClick={() => { setAktifKelime(kelimeData.bekleyenler[0]); setCevapGosterim(false); }} className="w-full bg-gradient-to-r from-cyan-500 to-blue-600 text-white rounded-xl p-4 shadow-md">
                    <div className="text-lg font-bold">🧠 Tekrara Başla</div><div className="text-xs opacity-80">{kelimeData.bekleyenler.length} kelime bekliyor</div>
                  </button>
                ) : (
                  <div className="bg-white rounded-xl p-4 border-2 border-cyan-300 shadow-md text-center space-y-3">
                    <div className="text-xs text-gray-400">Kutu {aktifKelime.kutu}/5 • Tekrar #{(aktifKelime.tekrar_sayisi||0)+1}</div>
                    <div className="text-2xl font-bold text-cyan-700">{aktifKelime.kelime}</div>
                    {!cevapGosterim ? (
                      <Button onClick={() => setCevapGosterim(true)} className="bg-yellow-500 text-white">Anlamını Göster 👀</Button>
                    ) : (<>
                      <div className="bg-cyan-50 rounded-lg p-3"><p className="text-sm font-medium">{aktifKelime.anlam}</p>{aktifKelime.ornek_cumle && <p className="text-xs text-gray-500 mt-1 italic">"{aktifKelime.ornek_cumle}"</p>}</div>
                      <div className="flex gap-2">
                        <Button className="flex-1 bg-red-500 text-white text-sm" onClick={async () => { try { await axios.post(`${API}/ai/kelime-evrimi/cevapla`, { kelime_id: aktifKelime.id, dogru: false }); } catch(e) {} const kalan = kelimeData.bekleyenler.filter(k => k.id !== aktifKelime.id); setKelimeData({...kelimeData, bekleyenler: kalan}); setAktifKelime(kalan[0] || null); setCevapGosterim(false); if (!kalan[0]) toast({ title: "🎉 Tamamlandı!" }); }}>❌ Bilmiyordum</Button>
                        <Button className="flex-1 bg-green-500 text-white text-sm" onClick={async () => { try { await axios.post(`${API}/ai/kelime-evrimi/cevapla`, { kelime_id: aktifKelime.id, dogru: true }); } catch(e) {} const kalan = kelimeData.bekleyenler.filter(k => k.id !== aktifKelime.id); setKelimeData({...kelimeData, bekleyenler: kalan}); setAktifKelime(kalan[0] || null); setCevapGosterim(false); if (!kalan[0]) toast({ title: "🎉 Tamamlandı!" }); }}>✅ Biliyordum</Button>
                      </div>
                    </>)}
                  </div>
                )}
              </>)}

              {kelimeData?.bekleyenler?.length === 0 && !oyunData && (
                <div className="text-center py-8 text-gray-500"><div className="text-3xl mb-2">🎉</div><p className="text-sm">Bugün tekrar edilecek kelime yok!</p><p className="text-xs text-gray-400 mt-1">Yeni kelimeler okudukça eklenecek</p></div>
              )}
            </div>);
          })()}

        </div>)}

        {/* ═══ SIRALAMA (XP Lig Bazlı) ═══ */}
        {aktifSekme === "siralama" && (<div className="space-y-4">
          <h2 className="text-lg font-bold">🏆 Lig Sıralaması</h2>
          {xpDurum && (<div className="bg-gradient-to-r from-yellow-50 to-orange-50 rounded-2xl p-4 border border-yellow-100 flex items-center justify-between">
            <div><div className="text-2xl font-bold">{xpDurum.lig_label}</div><div className="text-sm text-gray-600">{xpDurum.toplam_xp} XP</div></div>
            {xpDurum.sonraki_lig && <div className="text-right"><div className="text-xs text-gray-500">Sonraki: {({"gumus":"🥈 Gümüş","altin":"🥇 Altın","elmas":"💎 Elmas"})[xpDurum.sonraki_lig]}</div><div className="text-sm font-bold text-orange-600">{xpDurum.kalan_xp} XP kaldı</div></div>}
          </div>)}
          {xpDurum?.son_xp?.length > 0 && (<div className="bg-white rounded-2xl p-3 shadow-sm border"><div className="text-xs font-medium text-gray-500 mb-2">Son Kazanımlar</div>
            {xpDurum.son_xp.slice(0,5).map((x,i) => (<div key={i} className="flex items-center justify-between py-1 text-xs"><span className="text-gray-600">{({"okuma_gorevi":"📖 Okuma","anlama_testi":"📝 Test","egzersiz":"🎯 Egzersiz","gorev_tamamla":"✅ Görev","gelisim_tamamla":"🎓 Gelişim","kitap_bitirme":"📚 Kitap","gunluk_streak":"🔥 Streak"})[x.eylem] || x.eylem}</span><span className="font-bold text-green-600">+{x.xp} XP</span></div>))}
          </div>)}
          <p className="text-xs text-gray-500">Toplam XP'ye göre sıralama</p>
          {ligSiralama && ligSiralama.siralama.length > 0 ? (<div className="bg-white rounded-2xl shadow-sm border overflow-hidden">
            {ligSiralama.siralama.map((s, i) => (<div key={i} className={`flex items-center justify-between px-4 py-3 ${s.ben ? 'bg-orange-50 border-l-4 border-l-orange-500 font-bold' : i%2===0 ? 'bg-white' : 'bg-gray-50'} ${i>0 ? 'border-t border-gray-100' : ''}`}>
              <div className="flex items-center gap-3"><div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${s.sira<=3 ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'}`}>{s.sira===1?"🥇":s.sira===2?"🥈":s.sira===3?"🥉":s.sira}</div><span className={`text-sm ${s.ben ? 'text-orange-700' : 'text-gray-700'}`}>{s.ad}</span><span className="text-xs">{s.lig_label}</span></div>
              <span className={`text-sm font-medium ${s.ben ? 'text-orange-600' : 'text-gray-500'}`}>{s.xp} XP</span>
            </div>))}
          </div>) : (<div className="text-center py-12"><div className="text-5xl mb-3">🏆</div><p className="text-gray-500">Henüz yeterli veri yok</p></div>)}
        </div>)}

        {/* ═══ MESAJLAR ═══ */}
        {aktifSekme === "mesajlar" && (<div className="space-y-4">
          <h2 className="text-lg font-bold">✉️ Mesajlar</h2>
          {profil?.ogretmen_bilgi && (
            <Card className="border-0 shadow-sm border-l-4 border-l-blue-500"><CardHeader className="pb-2"><CardTitle className="text-sm">📝 Öğretmenime Mesaj</CardTitle><p className="text-xs text-gray-500">{profil.ogretmen_bilgi.ad} {profil.ogretmen_bilgi.soyad}</p></CardHeader>
              <CardContent><form onSubmit={mesajGonder} className="space-y-3">
                <div><Label className="text-xs">Konu</Label><Input value={mesajForm.konu} onChange={e => setMesajForm({...mesajForm, konu: e.target.value})} placeholder="Konu..." className="text-sm" /></div>
                <div><Label className="text-xs">Mesaj *</Label><textarea value={mesajForm.icerik} onChange={e => setMesajForm({...mesajForm, icerik: e.target.value})} required placeholder="Mesajınızı yazın..." className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[80px]" /></div>
                <Button type="submit" disabled={mesajGonderiliyor || !mesajForm.icerik.trim()} className="w-full bg-blue-600 text-white text-sm">{mesajGonderiliyor ? "..." : "✉️ Gönder"}</Button>
              </form></CardContent>
            </Card>
          )}
          {!profil?.ogretmen_bilgi && (<div className="bg-yellow-50 rounded-xl p-4 border border-yellow-200 text-sm text-yellow-800">Henüz öğretmen atanmamış.</div>)}
          {mesajlar.length > 0 && (<><h3 className="text-xs font-medium text-gray-500">Geçmiş</h3>
            {mesajlar.map(m => { const ben = m.gonderen_id === user.id; return (
              <div key={m.id} className={`rounded-xl p-3 border ${ben ? 'bg-blue-50 border-blue-100 ml-8' : 'bg-white border-gray-100 mr-8'}`} onClick={() => !ben && !m.okundu && mesajOkundu(m.id)}>
                <div className="flex items-center justify-between mb-1"><span className="text-xs text-gray-500">{ben ? `Sen → ${m.alici_ad}` : `${m.gonderen_ad}`}</span><div className="flex items-center gap-1"><span className="text-[10px] text-gray-400">{new Date(m.tarih).toLocaleDateString('tr-TR')}</span>{!ben && !m.okundu && <span className="w-2 h-2 bg-red-500 rounded-full" />}</div></div>
                {m.konu && <div className="text-xs font-bold text-gray-700">{m.konu}</div>}
                <p className="text-sm text-gray-800 mt-0.5">{m.icerik}</p>
              </div>);
            })}</>)}
        </div>)}

      </div>
      <Toaster />
    </div>
  );
}


// ═══════════════════════════════════════════════
// MESAJLAR PANELİ — Tüm roller için ortak
// ═══════════════════════════════════════════════

function MesajlarPanel({ user }) {
  const { toast } = useToast();
  const [mesajlar, setMesajlar] = useState([]);
  const [kullanicilar, setKullanicilar] = useState([]);
  const [okunmamisSayisi, setOkunmamisSayisi] = useState(0);
  const [seciliAlici, setSeciliAlici] = useState("");
  const [form, setForm] = useState({ konu: "", icerik: "" });
  const [gonderiliyor, setGonderiliyor] = useState(false);
  const [gorunum, setGorunum] = useState("gelen"); // gelen, giden, yeni
  const [filtre, setFiltre] = useState("hepsi"); // hepsi, okunmamis

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${API}/mesajlar`); setMesajlar(Array.isArray(r.data) ? r.data : []); } catch(e) { setMesajlar([]); }
    try { const r = await axios.get(`${API}/mesajlar/okunmamis-sayisi`); setOkunmamisSayisi(r.data?.sayi || 0); } catch(e) {}
    try { const r = await axios.get(`${API}/auth/users`); setKullanicilar(Array.isArray(r.data) ? r.data : []); } catch(e) { setKullanicilar([]); }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const gelenMesajlar = mesajlar.filter(m => m.alici_id === user.id);
  const gidenMesajlar = mesajlar.filter(m => m.gonderen_id === user.id);
  const okunmamislar = gelenMesajlar.filter(m => !m.okundu);

  // Alıcı listesi role göre filtrele
  const aliciListesi = kullanicilar.filter(u => u.id !== user.id).map(u => ({
    id: u.id,
    ad: `${u.ad || ""} ${u.soyad || ""}`.trim(),
    rol: u.role,
    rolLabel: ({ admin: "Yönetici", coordinator: "Koordinatör", teacher: "Öğretmen", student: "Öğrenci", parent: "Veli" })[u.role] || u.role,
  }));

  const mesajGonder = async (e) => {
    e.preventDefault();
    if (!seciliAlici) { toast({ title: "Alıcı seçmelisiniz", variant: "destructive" }); return; }
    setGonderiliyor(true);
    try {
      await axios.post(`${API}/mesajlar`, { alici_id: seciliAlici, konu: form.konu, icerik: form.icerik });
      toast({ title: "✉️ Mesaj gönderildi!" });
      setForm({ konu: "", icerik: "" }); setSeciliAlici(""); setGorunum("giden"); fetchAll();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
    setGonderiliyor(false);
  };

  const mesajOkundu = async (id) => { try { await axios.put(`${API}/mesajlar/${id}/okundu`); fetchAll(); } catch(e) {} };

  const rolRenk = (r) => ({ admin: "bg-red-100 text-red-700", coordinator: "bg-orange-100 text-orange-700", teacher: "bg-blue-100 text-blue-700", student: "bg-green-100 text-green-700", parent: "bg-purple-100 text-purple-700" })[r] || "bg-gray-100 text-gray-600";

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Mesajlar</h2>
          <p className="text-gray-500 text-sm mt-1">{okunmamisSayisi > 0 ? `${okunmamisSayisi} okunmamış mesaj` : "Tüm mesajlar okundu"}</p>
        </div>
        <Button onClick={() => setGorunum("yeni")} className="bg-gradient-to-r from-blue-500 to-indigo-600 text-white">
          <Send className="h-4 w-4 mr-2" /> Yeni Mesaj
        </Button>
      </div>

      {/* Görünüm Seçici */}
      <div className="flex gap-2">
        {[
          { v: "gelen", l: "Gelen Kutusu", badge: okunmamisSayisi },
          { v: "giden", l: "Gönderilenler" },
          { v: "yeni", l: "Yeni Mesaj" },
        ].map(t => (
          <button key={t.v} onClick={() => setGorunum(t.v)}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-all border flex items-center gap-2 ${gorunum === t.v ? 'bg-blue-500 text-white border-blue-500 shadow' : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'}`}>
            {t.l}
            {t.badge > 0 && <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${gorunum === t.v ? 'bg-white/30' : 'bg-red-100 text-red-600'}`}>{t.badge}</span>}
          </button>
        ))}
      </div>

      {/* Yeni Mesaj */}
      {gorunum === "yeni" && (
        <Card className="border-0 shadow-sm">
          <CardHeader><CardTitle className="text-base flex items-center gap-2"><Send className="h-4 w-4" /> Yeni Mesaj</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={mesajGonder} className="space-y-4">
              <div>
                <Label>Alıcı *</Label>
                <Select value={seciliAlici} onValueChange={setSeciliAlici}>
                  <SelectTrigger><SelectValue placeholder="Kişi seçin..." /></SelectTrigger>
                  <SelectContent>
                    {["admin", "coordinator", "teacher", "student", "parent"].map(rol => {
                      const kisiler = aliciListesi.filter(k => k.rol === rol);
                      if (kisiler.length === 0) return null;
                      return kisiler.map(k => (
                        <SelectItem key={k.id} value={k.id}>
                          <span className="flex items-center gap-2">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${rolRenk(k.rol)}`}>{k.rolLabel}</span>
                            {k.ad}
                          </span>
                        </SelectItem>
                      ));
                    })}
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Konu</Label><Input value={form.konu} onChange={e => setForm({...form, konu: e.target.value})} placeholder="Mesaj konusu..." /></div>
              <div><Label>Mesaj *</Label><textarea value={form.icerik} onChange={e => setForm({...form, icerik: e.target.value})} required placeholder="Mesajınızı yazın..." className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[120px]" /></div>
              <div className="flex gap-3">
                <Button type="submit" disabled={gonderiliyor || !form.icerik.trim()} className="flex-1 bg-blue-600 text-white">{gonderiliyor ? "Gönderiliyor..." : "✉️ Gönder"}</Button>
                <Button type="button" variant="outline" onClick={() => setGorunum("gelen")} className="flex-1">İptal</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Gelen Kutusu */}
      {gorunum === "gelen" && (
        <div className="space-y-3">
          <div className="flex gap-2 mb-2">
            <button onClick={() => setFiltre("hepsi")} className={`text-xs px-3 py-1 rounded-full border ${filtre === "hepsi" ? 'bg-gray-800 text-white' : 'bg-white text-gray-600'}`}>Tümü ({gelenMesajlar.length})</button>
            <button onClick={() => setFiltre("okunmamis")} className={`text-xs px-3 py-1 rounded-full border ${filtre === "okunmamis" ? 'bg-red-500 text-white' : 'bg-white text-gray-600'}`}>Okunmamış ({okunmamislar.length})</button>
          </div>
          {(filtre === "okunmamis" ? okunmamislar : gelenMesajlar).length === 0 ? (
            <div className="text-center py-12"><Mail className="h-12 w-12 text-gray-300 mx-auto mb-3" /><p className="text-gray-500">{filtre === "okunmamis" ? "Okunmamış mesaj yok" : "Gelen mesaj yok"}</p></div>
          ) : (
            (filtre === "okunmamis" ? okunmamislar : gelenMesajlar).map(m => (
              <Card key={m.id} className={`border-0 shadow-sm cursor-pointer transition-all hover:shadow-md ${!m.okundu ? 'border-l-4 border-l-blue-500 bg-blue-50/30' : ''}`} onClick={() => !m.okundu && mesajOkundu(m.id)}>
                <CardContent className="p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${rolRenk(m.gonderen_rol)}`}>{({admin:"Yönetici",coordinator:"Koord.",teacher:"Öğretmen",student:"Öğrenci",parent:"Veli"})[m.gonderen_rol]}</span>
                        <span className="font-medium text-sm text-gray-900">{m.gonderen_ad}</span>
                        {!m.okundu && <span className="w-2 h-2 bg-blue-500 rounded-full" />}
                      </div>
                      {m.konu && <div className="font-bold text-sm text-gray-800 mt-1">{m.konu}</div>}
                      <p className="text-sm text-gray-600 mt-1 line-clamp-2">{m.icerik}</p>
                    </div>
                    <div className="text-xs text-gray-400 whitespace-nowrap">{new Date(m.tarih).toLocaleDateString('tr-TR')}</div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {/* Gönderilenler */}
      {gorunum === "giden" && (
        <div className="space-y-3">
          {gidenMesajlar.length === 0 ? (
            <div className="text-center py-12"><Send className="h-12 w-12 text-gray-300 mx-auto mb-3" /><p className="text-gray-500">Gönderilen mesaj yok</p></div>
          ) : (
            gidenMesajlar.map(m => (
              <Card key={m.id} className="border-0 shadow-sm"><CardContent className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-xs text-gray-500">→</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${rolRenk(m.alici_rol)}`}>{({admin:"Yönetici",coordinator:"Koord.",teacher:"Öğretmen",student:"Öğrenci",parent:"Veli"})[m.alici_rol]}</span>
                      <span className="font-medium text-sm text-gray-900">{m.alici_ad}</span>
                      {m.okundu ? <span className="text-xs text-green-600">✓ okundu</span> : <span className="text-xs text-gray-400">gönderildi</span>}
                    </div>
                    {m.konu && <div className="font-bold text-sm text-gray-800 mt-1">{m.konu}</div>}
                    <p className="text-sm text-gray-600 mt-1 line-clamp-2">{m.icerik}</p>
                  </div>
                  <div className="text-xs text-gray-400 whitespace-nowrap">{new Date(m.tarih).toLocaleDateString('tr-TR')}</div>
                </div>
              </CardContent></Card>
            ))
          )}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════
// VELİ PANELİ
// ═══════════════════════════════════════════════

function VeliPaneli({ user, logout }) {
  const { toast } = useToast();
  const [cocuklar, setCocuklar] = useState([]);
  const [seciliCocuk, setSeciliCocuk] = useState(null);
  const [okumaKayitlari, setOkumaKayitlari] = useState([]);
  const [istatistik, setIstatistik] = useState(null);
  const [gorevler, setGorevler] = useState([]);
  const [aktifSekme, setAktifSekme] = useState("ozet");
  // Mesaj
  const [mesajlar, setMesajlar] = useState([]);
  const [kullanicilar, setKullanicilar] = useState([]);
  const [seciliAlici, setSeciliAlici] = useState("");
  const [mesajForm, setMesajForm] = useState({ konu: "", icerik: "" });
  const [mesajGonderiliyor, setMesajGonderiliyor] = useState(false);
  const [okunmamisSayisi, setOkunmamisSayisi] = useState(0);
  const [mesajGorunum, setMesajGorunum] = useState("gelen");
  // Anket
  const [anketSorulari, setAnketSorulari] = useState([]);
  const [anketYanitlar, setAnketYanitlar] = useState({});
  const [anketTavsiye, setAnketTavsiye] = useState(null);
  const [anketNot, setAnketNot] = useState("");
  const [anketGonderiliyor, setAnketGonderiliyor] = useState(false);
  const [veliAnketleri, setVeliAnketleri] = useState([]);

  // Velinin çocuklarını bul (linked_id ile eşleşen öğrenciler)
  useEffect(() => {
    const fetchCocuklar = async () => {
      try {
        const r = await axios.get(`${API}/students`);
        const data = Array.isArray(r.data) ? r.data : [];
        const linkedId = user.linked_id;
        let cocuklist = [];
        if (linkedId) {
          cocuklist = data.filter(s => s.id === linkedId);
        }
        if (cocuklist.length === 0) {
          cocuklist = data.filter(s => s.veli_telefon && user.telefon && s.veli_telefon === user.telefon);
        }
        setCocuklar(cocuklist);
        if (cocuklist.length > 0 && !seciliCocuk) setSeciliCocuk(cocuklist[0]);
      } catch(e) { setCocuklar([]); }
    };
    fetchCocuklar();
  }, [user]);

  const fetchCocukVerileri = useCallback(async () => {
    if (!seciliCocuk) return;
    try { const r = await axios.get(`${API}/reading-logs/${seciliCocuk.id}`); setOkumaKayitlari(Array.isArray(r.data) ? r.data : []); } catch(e) { setOkumaKayitlari([]); }
    try { const r = await axios.get(`${API}/reading-logs/${seciliCocuk.id}/istatistik`); setIstatistik(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/gorevler?hedef_id=${seciliCocuk.id}&hedef_tip=ogrenci`); setGorevler(Array.isArray(r.data) ? r.data : []); } catch(e) { setGorevler([]); }
  }, [seciliCocuk]);

  useEffect(() => { fetchCocukVerileri(); }, [fetchCocukVerileri]);

  // Mesajlar
  useEffect(() => {
    axios.get(`${API}/mesajlar`).then(r => setMesajlar(Array.isArray(r.data) ? r.data : [])).catch(() => { setMesajlar([]); });
    axios.get(`${API}/mesajlar/okunmamis-sayisi`).then(r => setOkunmamisSayisi(r.data?.sayi || 0)).catch(() => {});
    axios.get(`${API}/anketler/sorular`).then(r => setAnketSorulari(Array.isArray(r.data) ? r.data : [])).catch(() => {});
    axios.get(`${API}/anketler/veli/${user.id}`).then(r => setVeliAnketleri(Array.isArray(r.data) ? r.data : [])).catch(() => {});
    axios.get(`${API}/auth/users`).then(r => { const d = Array.isArray(r.data) ? r.data : []; setKullanicilar(d.filter(u => u.role === "teacher" || u.role === "admin" || u.role === "coordinator")); }).catch(() => {});
  }, []);

  const mesajGonder = async (e) => {
    e.preventDefault();
    if (!seciliAlici) { toast({ title: "Alıcı seçin", variant: "destructive" }); return; }
    setMesajGonderiliyor(true);
    try {
      await axios.post(`${API}/mesajlar`, { alici_id: seciliAlici, konu: mesajForm.konu, icerik: mesajForm.icerik });
      toast({ title: "✉️ Mesaj gönderildi!" }); setMesajForm({ konu: "", icerik: "" }); setSeciliAlici("");
      const r = await axios.get(`${API}/mesajlar`); setMesajlar(r.data);
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
    setMesajGonderiliyor(false);
  };

  const mesajOkundu = async (id) => { try { await axios.put(`${API}/mesajlar/${id}/okundu`); const r = await axios.get(`${API}/mesajlar`); setMesajlar(r.data); const r2 = await axios.get(`${API}/mesajlar/okunmamis-sayisi`); setOkunmamisSayisi(r2.data.sayi); } catch(e) {} };

  const bekleyenGorevler = gorevler.filter(g => g.durum !== "tamamlandi");
  const gelenMesajlar = mesajlar.filter(m => m.alici_id === user.id);
  const gidenMesajlar = mesajlar.filter(m => m.gonderen_id === user.id);

  const sekmeler = [
    { id: "ozet", label: "Özet", icon: "📊" },
    { id: "okumalar", label: "Okumalar", icon: "📖" },
    { id: "gorevler", label: "Görevler", icon: "📌" },
    { id: "anket", label: "Değerlendir", icon: "⭐" },
    { id: "mesajlar", label: "Mesajlar", icon: "✉️", badge: okunmamisSayisi || null },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-purple-400 to-pink-500 rounded-xl flex items-center justify-center"><BookOpen className="h-5 w-5 text-white" /></div>
            <div><div className="font-bold text-gray-900 text-sm">{user.ad} {user.soyad}</div><div className="text-xs text-gray-500">Veli Paneli</div></div>
          </div>
          <div className="flex items-center gap-2">
            <BildirimZili user={user} />
            <Button variant="outline" size="sm" onClick={logout} className="text-xs"><LogOut className="h-3 w-3 mr-1" />Çıkış</Button>
          </div>
        </div>
      </div>

      {/* Çocuk seçici */}
      {cocuklar.length > 1 && (
        <div className="bg-white border-b px-4 py-2">
          <div className="max-w-2xl mx-auto flex gap-2">
            {cocuklar.map(c => (
              <button key={c.id} onClick={() => setSeciliCocuk(c)}
                className={`px-3 py-1.5 rounded-xl text-xs font-medium border ${seciliCocuk?.id === c.id ? 'bg-purple-500 text-white border-purple-500' : 'bg-white text-gray-600 border-gray-200'}`}>
                {c.ad} {c.soyad}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white border-b sticky top-[60px] z-10">
        <div className="max-w-2xl mx-auto px-2 flex gap-1 overflow-x-auto py-2">
          {sekmeler.map(s => (
            <button key={s.id} onClick={() => setAktifSekme(s.id)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium whitespace-nowrap transition-all ${aktifSekme === s.id ? 'bg-purple-500 text-white shadow' : 'text-gray-600 hover:bg-gray-100'}`}>
              {s.icon} {s.label}
              {s.badge && <span className={`px-1.5 py-0.5 rounded-full text-[10px] font-bold ${aktifSekme === s.id ? 'bg-white/30' : 'bg-red-100 text-red-600'}`}>{s.badge}</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="max-w-2xl mx-auto p-4 space-y-5">
        {!seciliCocuk && cocuklar.length === 0 ? (
          <div className="text-center py-16"><div className="text-5xl mb-4">👶</div><h3 className="font-bold text-gray-900">Çocuk kaydı bulunamadı</h3><p className="text-gray-500 text-sm mt-1">Lütfen yöneticinize başvurun.</p></div>
        ) : (<>

          {/* ÖZET */}
          {aktifSekme === "ozet" && seciliCocuk && (<>
            <div className="bg-white rounded-2xl p-4 shadow-sm border">
              <h3 className="font-bold text-lg">{seciliCocuk.ad} {seciliCocuk.soyad}</h3>
              <p className="text-sm text-gray-500">{seciliCocuk.sinif && `${seciliCocuk.sinif}. sınıf`} {seciliCocuk.kur && `• Kur: ${seciliCocuk.kur}`}</p>
            </div>
            {istatistik && (<div className="grid grid-cols-3 gap-3">
              <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-orange-600">{istatistik.streak}</div><div className="text-xs text-gray-500">🔥 Streak</div></div>
              <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-green-600">{istatistik.bugun_dakika}</div><div className="text-xs text-gray-500">⏱ Bugün</div></div>
              <div className="bg-white rounded-2xl p-3 text-center shadow-sm border"><div className="text-2xl font-bold text-blue-600">{istatistik.toplam_kitap}</div><div className="text-xs text-gray-500">📚 Kitap</div></div>
            </div>)}
            {istatistik && (<div className="bg-white rounded-2xl p-4 shadow-sm border"><div className="text-sm font-medium text-gray-700 mb-2">Bu Hafta</div><div className="flex items-center gap-2"><div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden"><div className="h-full bg-gradient-to-r from-purple-400 to-pink-500 rounded-full" style={{ width: `${Math.min(100,(istatistik.aktif_gunler_7/4)*100)}%` }} /></div><span className="text-sm font-bold">{istatistik.aktif_gunler_7}/4 gün</span></div></div>)}
            {istatistik && (<div className="bg-gradient-to-r from-purple-50 to-pink-50 rounded-2xl p-4 text-center border"><div className="text-3xl font-bold text-purple-600">{istatistik.toplam_dakika}</div><div className="text-sm text-gray-500">toplam dakika okuma</div></div>)}

            {/* 🤖 AI Gelişim Raporu */}
            {istatistik && (
              <div className="bg-gradient-to-r from-cyan-50 to-blue-50 rounded-2xl p-4 border border-cyan-200">
                <div className="flex items-center gap-2 mb-3"><span className="text-lg">🤖</span><span className="font-bold text-sm text-cyan-800">AI Gelişim Raporu</span></div>
                <div className="space-y-2 text-xs text-gray-600">
                  <div className="flex items-center justify-between"><span>📚 Bu ay okunan kitap</span><span className="font-bold text-blue-600">{istatistik.toplam_kitap || 0}</span></div>
                  <div className="flex items-center justify-between"><span>🔥 Mevcut streak</span><span className="font-bold text-orange-600">{istatistik.streak || 0} gün</span></div>
                  <div className="flex items-center justify-between"><span>⏱ Günlük ortalama</span><span className="font-bold text-green-600">{Math.round((istatistik.toplam_dakika || 0) / Math.max(istatistik.aktif_gunler_7 || 1, 1))} dk</span></div>
                  {istatistik.streak >= 5 && <div className="bg-green-100 rounded-lg p-2 text-green-700 text-center">🎉 Harika! Çocuğunuz {istatistik.streak} gündür düzenli okuyor</div>}
                  {istatistik.streak < 2 && <div className="bg-yellow-100 rounded-lg p-2 text-yellow-700 text-center">💡 Birlikte 10 dakika okuma, alışkanlık oluşturur</div>}
                  {istatistik.streak >= 2 && istatistik.streak < 5 && <div className="bg-blue-100 rounded-lg p-2 text-blue-700 text-center">👏 İyi gidiyor! Streak'i sürdürmek için bugün de okuyalım</div>}
                </div>
              </div>
            )}
            {bekleyenGorevler.length > 0 && (<div className="bg-yellow-50 rounded-2xl p-4 border border-yellow-100"><div className="font-medium text-sm text-yellow-800">📌 {bekleyenGorevler.length} bekleyen görev var</div><div className="mt-2 space-y-1">{bekleyenGorevler.slice(0,3).map(g => (<div key={g.id} className="text-xs text-gray-600">• {g.baslik}{g.son_tarih && ` (Son: ${new Date(g.son_tarih).toLocaleDateString('tr-TR')})`}</div>))}</div></div>)}
          </>)}

          {/* OKUMALAR */}
          {aktifSekme === "okumalar" && (<div className="space-y-3"><h2 className="text-xl font-bold">📖 Okuma Geçmişi</h2>
            {okumaKayitlari.length === 0 ? <p className="text-center text-gray-500 py-8">Henüz okuma kaydı yok</p> : (
              okumaKayitlari.map(k => (<div key={k.id} className="bg-white rounded-xl p-3 shadow-sm border flex items-center justify-between"><div><div className="font-medium text-sm">{k.kitap_adi || "—"}</div><div className="text-xs text-gray-400">{k.bolum && `${k.bolum} • `}⏱ {k.sure_dakika} dk</div></div><div className="text-xs text-gray-400">{new Date(k.tarih).toLocaleDateString('tr-TR')}</div></div>))
            )}
          </div>)}

          {/* GÖREVLER */}
          {aktifSekme === "gorevler" && (<div className="space-y-3"><h2 className="text-xl font-bold">📌 Görevler</h2>
            {gorevler.length === 0 ? <p className="text-center text-gray-500 py-8">Görev yok</p> : (
              gorevler.map(g => (<div key={g.id} className={`bg-white rounded-xl p-3 shadow-sm border ${g.durum === "tamamlandi" ? "opacity-60" : ""}`}>
                <div className="flex items-center justify-between"><div className="font-medium text-sm">{g.durum === "tamamlandi" ? "✅ " : ""}{g.baslik}</div><span className={`text-xs px-2 py-0.5 rounded-full ${g.durum === "tamamlandi" ? "bg-green-100 text-green-700" : g.durum === "bekliyor" ? "bg-yellow-100 text-yellow-700" : "bg-blue-100 text-blue-700"}`}>{g.durum === "tamamlandi" ? "Tamamlandı" : g.durum === "bekliyor" ? "Bekliyor" : "Devam"}</span></div>
                {g.son_tarih && <div className="text-xs text-gray-400 mt-1">Son: {new Date(g.son_tarih).toLocaleDateString('tr-TR')}</div>}
              </div>))
            )}
          </div>)}

          {/* MESAJLAR */}
          {/* ANKET */}
          {aktifSekme === "anket" && (<div className="space-y-4">
            <h2 className="text-xl font-bold">⭐ Öğretmen Değerlendirmesi</h2>
            {seciliCocuk ? (<>
              {(() => {
                const ogretmenId = seciliCocuk.ogretmen_id;
                const donem = new Date().getFullYear() + "-D" + String(new Date().getMonth() + 1).padStart(2, '0');
                const zatenDoldurdu = veliAnketleri.some(a => a.ogretmen_id === ogretmenId && a.donem === donem);

                if (zatenDoldurdu) return (
                  <div className="bg-green-50 rounded-2xl p-6 border border-green-200 text-center">
                    <div className="text-4xl mb-2">✅</div><h3 className="font-bold text-green-800">Bu dönem için değerlendirmenizi yaptınız</h3>
                    <p className="text-sm text-green-600 mt-1">Teşekkür ederiz! Sonraki dönemde tekrar doldurabilirsiniz.</p>
                  </div>
                );

                const anketGonder = async () => {
                  const puanSorular = anketSorulari.filter(s => s.tip === "puan");
                  const bos = puanSorular.filter(s => !anketYanitlar[s.no]);
                  if (bos.length > 0) { toast({ title: "Lütfen tüm soruları puanlayın", variant: "destructive" }); return; }
                  if (anketTavsiye === null) { toast({ title: "Tavsiye sorusunu cevaplayın", variant: "destructive" }); return; }
                  setAnketGonderiliyor(true);
                  try {
                    const yanitlar = Object.entries(anketYanitlar).map(([no, puan]) => {
                      const s = anketSorulari.find(q => q.no === parseInt(no));
                      return { soru_no: parseInt(no), puan, kategori: s?.kategori || "" };
                    });
                    await axios.post(`${API}/anketler`, { ogretmen_id: ogretmenId, ogrenci_id: seciliCocuk.id, yanitlar, tavsiye: anketTavsiye, not_text: anketNot, donem });
                    toast({ title: "⭐ Değerlendirmeniz kaydedildi! Teşekkürler." });
                    setAnketYanitlar({}); setAnketTavsiye(null); setAnketNot("");
                    axios.get(`${API}/anketler/veli/${user.id}`).then(r => setVeliAnketleri(Array.isArray(r.data) ? r.data : []));
                  } catch(e) { toast({ title: e.response?.data?.detail || "Hata", variant: "destructive" }); }
                  setAnketGonderiliyor(false);
                };

                return (
                  <Card className="border-0 shadow-sm"><CardContent className="p-5 space-y-5">
                    <p className="text-sm text-gray-600">{seciliCocuk.ad} {seciliCocuk.soyad}'ın öğretmenini değerlendirin. Yanıtlarınız anonim olarak iletilir.</p>
                    {anketSorulari.filter(s => s.tip === "puan").map(s => (
                      <div key={s.no}>
                        <Label className="text-sm font-medium">{s.no}. {s.soru}</Label>
                        <div className="flex gap-1 mt-2">{[1,2,3,4,5].map(p => (
                          <button key={p} onClick={() => setAnketYanitlar({...anketYanitlar, [s.no]: p})}
                            className={`w-10 h-10 rounded-xl text-lg transition-all ${(anketYanitlar[s.no] || 0) >= p ? 'bg-yellow-400 shadow-sm scale-110' : 'bg-gray-100 hover:bg-gray-200'}`}>⭐</button>
                        ))}</div>
                      </div>
                    ))}
                    <div>
                      <Label className="text-sm font-medium">8. Bu öğretmeni başka velilere tavsiye eder misiniz?</Label>
                      <div className="flex gap-3 mt-2">
                        <button onClick={() => setAnketTavsiye(true)} className={`flex-1 py-3 rounded-xl text-sm font-medium border transition-all ${anketTavsiye === true ? 'bg-green-500 text-white border-green-500' : 'bg-white text-gray-600 border-gray-200'}`}>👍 Evet</button>
                        <button onClick={() => setAnketTavsiye(false)} className={`flex-1 py-3 rounded-xl text-sm font-medium border transition-all ${anketTavsiye === false ? 'bg-red-500 text-white border-red-500' : 'bg-white text-gray-600 border-gray-200'}`}>👎 Hayır</button>
                      </div>
                    </div>
                    <div><Label className="text-sm">9. Eklemek istediğiniz not (opsiyonel)</Label><textarea value={anketNot} onChange={e => setAnketNot(e.target.value)} className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[60px] mt-1" placeholder="Düşünceleriniz..." /></div>
                    <Button onClick={anketGonder} disabled={anketGonderiliyor} className="w-full bg-purple-600 text-white py-3">{anketGonderiliyor ? "Gönderiliyor..." : "⭐ Değerlendirmeyi Gönder"}</Button>
                  </CardContent></Card>
                );
              })()}
            </>) : (<div className="text-center py-12 text-gray-500">Çocuk seçilmedi</div>)}

            {/* Önceki anketler */}
            {veliAnketleri.length > 0 && (<div><h3 className="text-sm font-medium text-gray-500 mt-4">Önceki Değerlendirmelerim</h3>
              {veliAnketleri.map(a => {
                const puanlar = (a.yanitlar || []).filter(y => y.puan).map(y => y.puan);
                const ort = puanlar.length > 0 ? (puanlar.reduce((t,p) => t+p, 0) / puanlar.length).toFixed(1) : "—";
                return (<div key={a.id} className="bg-white rounded-xl p-3 border mt-2 flex items-center justify-between"><div><div className="text-sm font-medium">⭐ {ort} / 5</div><div className="text-xs text-gray-400">{a.donem} • {a.tavsiye ? "👍 Tavsiye" : "👎"}</div></div><div className="text-xs text-gray-400">{new Date(a.tarih).toLocaleDateString('tr-TR')}</div></div>);
              })}
            </div>)}
          </div>)}

          {aktifSekme === "mesajlar" && (<div className="space-y-4">
            <h2 className="text-xl font-bold">✉️ Mesajlar</h2>
            <div className="flex gap-2">
              {[{v:"gelen",l:`Gelen (${gelenMesajlar.length})`},{v:"giden",l:"Gönderilen"},{v:"yeni",l:"Yeni Mesaj"}].map(t => (
                <button key={t.v} onClick={() => setMesajGorunum(t.v)} className={`px-3 py-1.5 rounded-xl text-xs font-medium border ${mesajGorunum === t.v ? 'bg-purple-500 text-white border-purple-500' : 'bg-white text-gray-600 border-gray-200'}`}>{t.l}</button>
              ))}
            </div>

            {mesajGorunum === "yeni" && (
              <Card className="border-0 shadow-sm"><CardContent className="p-4"><form onSubmit={mesajGonder} className="space-y-3">
                <div><Label className="text-xs">Alıcı *</Label>
                  <Select value={seciliAlici} onValueChange={setSeciliAlici}><SelectTrigger className="text-sm"><SelectValue placeholder="Öğretmen seçin..." /></SelectTrigger>
                    <SelectContent>{kullanicilar.map(u => (<SelectItem key={u.id} value={u.id}>{u.ad} {u.soyad} ({({admin:"Yönetici",coordinator:"Koord.",teacher:"Öğretmen"})[u.role]})</SelectItem>))}</SelectContent>
                  </Select></div>
                <div><Label className="text-xs">Konu</Label><Input value={mesajForm.konu} onChange={e => setMesajForm({...mesajForm, konu: e.target.value})} placeholder="Konu..." className="text-sm" /></div>
                <div><Label className="text-xs">Mesaj *</Label><textarea value={mesajForm.icerik} onChange={e => setMesajForm({...mesajForm, icerik: e.target.value})} required placeholder="Mesajınızı yazın..." className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[80px]" /></div>
                <Button type="submit" disabled={mesajGonderiliyor} className="w-full bg-purple-600 text-white text-sm">{mesajGonderiliyor ? "..." : "✉️ Gönder"}</Button>
              </form></CardContent></Card>
            )}

            {mesajGorunum === "gelen" && (<div className="space-y-2">
              {gelenMesajlar.length === 0 ? <p className="text-center text-gray-500 py-8">Gelen mesaj yok</p> : (
                gelenMesajlar.map(m => (<div key={m.id} className={`bg-white rounded-xl p-3 border ${!m.okundu ? 'border-l-4 border-l-purple-500 bg-purple-50/30' : ''}`} onClick={() => !m.okundu && mesajOkundu(m.id)}>
                  <div className="flex items-center justify-between"><span className="font-medium text-sm">{m.gonderen_ad}</span><span className="text-xs text-gray-400">{new Date(m.tarih).toLocaleDateString('tr-TR')}</span></div>
                  {m.konu && <div className="text-xs font-bold text-gray-700 mt-1">{m.konu}</div>}
                  <p className="text-sm text-gray-600 mt-1">{m.icerik}</p>
                </div>))
              )}
            </div>)}

            {mesajGorunum === "giden" && (<div className="space-y-2">
              {gidenMesajlar.length === 0 ? <p className="text-center text-gray-500 py-8">Gönderilen mesaj yok</p> : (
                gidenMesajlar.map(m => (<div key={m.id} className="bg-white rounded-xl p-3 border">
                  <div className="flex items-center justify-between"><span className="font-medium text-sm">→ {m.alici_ad}</span><span className="text-xs text-gray-400">{new Date(m.tarih).toLocaleDateString('tr-TR')}</span></div>
                  {m.konu && <div className="text-xs font-bold text-gray-700 mt-1">{m.konu}</div>}
                  <p className="text-sm text-gray-600 mt-1">{m.icerik}</p>
                </div>))
              )}
            </div>)}
          </div>)}

        </>)}
      </div>
      <Toaster />
    </div>
  );
}

// ═══════════════════════════════════════════════
// SİSTEM AYARLARI — Admin panel (Rozet, XP, Lig, Anket yönetimi)
// ═══════════════════════════════════════════════

function SistemAyarlari({ user }) {
  const { toast } = useToast();
  const [ayarSekme, setAyarSekme] = useState("xp");
  const [xpTablosu, setXpTablosu] = useState({ okuma_gorevi: 10, anlama_testi: 15, kelime_gorevi: 8, gunluk_streak: 5, kitap_bitirme: 30, yazili_ozet: 20, egzersiz: 5, gelisim_tamamla: 5, gorev_tamamla: 10 });
  const [ligEsikleri, setLigEsikleri] = useState({ bronz: 0, gumus: 200, altin: 500, elmas: 1000 });
  const [ogretmenRozetler, setOgretmenRozetler] = useState([
    {kod:"icerik_ilk",ad:"İlk Adım",ikon:"🌱",kategori:"icerik",seviye:"bronz",puan:5},
    {kod:"icerik_5",ad:"İçerik Üreticisi",ikon:"✍️",kategori:"icerik",seviye:"gumus",puan:10},
    {kod:"icerik_20",ad:"Kütüphane Kurucusu",ikon:"📚",kategori:"icerik",seviye:"altin",puan:25},
    {kod:"icerik_50",ad:"Bilgi Kaynağı",ikon:"🏛️",kategori:"icerik",seviye:"elmas",puan:50},
    {kod:"oy_ilk",ad:"İlk Oy",ikon:"🗳️",kategori:"kalite",seviye:"bronz",puan:3},
    {kod:"oy_20",ad:"Kalite Bekçisi",ikon:"🛡️",kategori:"kalite",seviye:"gumus",puan:10},
    {kod:"oy_50",ad:"Baş Editör",ikon:"📋",kategori:"kalite",seviye:"altin",puan:25},
    {kod:"gorev_ilk",ad:"İlk Görev",ikon:"📌",kategori:"egitimci",seviye:"bronz",puan:3},
    {kod:"gorev_20",ad:"Aktif Eğitimci",ikon:"🎯",kategori:"egitimci",seviye:"gumus",puan:15},
    {kod:"ilham_veren",ad:"İlham Veren",ikon:"💡",kategori:"egitimci",seviye:"altin",puan:20},
    {kod:"yildiz_egitimci",ad:"Yıldız Eğitimci",ikon:"⭐",kategori:"egitimci",seviye:"elmas",puan:40},
    {kod:"kur_ilk",ad:"İlk Kur Atlatan",ikon:"🎓",kategori:"kur",seviye:"bronz",puan:10},
    {kod:"kur_20",ad:"Kur Ustası",ikon:"🏅",kategori:"kur",seviye:"gumus",puan:25},
    {kod:"kur_30",ad:"Seviye Atlatan",ikon:"🚀",kategori:"kur",seviye:"altin",puan:40},
    {kod:"kur_50",ad:"Süper Eğitimci",ikon:"🦸",kategori:"kur",seviye:"platin",puan:75},
    {kod:"kur_100",ad:"Dönüşüm Lideri",ikon:"👑",kategori:"kur",seviye:"elmas",puan:100},
    {kod:"veli_ilk",ad:"İlk Beğeni",ikon:"👍",kategori:"veli",seviye:"bronz",puan:5},
    {kod:"veli_20",ad:"Veli Favorisi",ikon:"💜",kategori:"veli",seviye:"gumus",puan:20},
    {kod:"veli_30",ad:"Ailelerin Güveni",ikon:"🏠",kategori:"veli",seviye:"altin",puan:35},
    {kod:"veli_100",ad:"Efsane Öğretmen",ikon:"🌟",kategori:"veli",seviye:"elmas",puan:100},
    {kod:"gelisim_ilk",ad:"Meraklı Öğretmen",ikon:"🔍",kategori:"gelisim",seviye:"bronz",puan:3},
    {kod:"gelisim_10",ad:"Sürekli Öğrenen",ikon:"📖",kategori:"gelisim",seviye:"gumus",puan:15},
    {kod:"gelisim_uzman",ad:"Uzman Öğretmen",ikon:"🎓",kategori:"gelisim",seviye:"elmas",puan:50},
    {kod:"mesaj_ilk",ad:"İlk Mesaj",ikon:"💬",kategori:"iletisim",seviye:"bronz",puan:2},
    {kod:"kopru_kurucu",ad:"Köprü Kurucu",ikon:"🌉",kategori:"iletisim",seviye:"altin",puan:15},
    {kod:"egz_ilk",ad:"İlk Egzersiz",ikon:"👁️",kategori:"egzersiz",seviye:"bronz",puan:2},
    {kod:"egz_tamset",ad:"Tam Set",ikon:"🎖️",kategori:"egzersiz",seviye:"altin",puan:20},
  ]);
  const [ogrenciRozetler, setOgrenciRozetler] = useState([
    {kod:"okuma_ilk",ad:"İlk Sayfa",ikon:"📖",kategori:"okuma",seviye:"bronz",xp:5},
    {kod:"okuma_100",ad:"Kitap Kurdu",ikon:"🐛",kategori:"okuma",seviye:"gumus",xp:15},
    {kod:"okuma_500",ad:"Okuma Yıldızı",ikon:"⭐",kategori:"okuma",seviye:"altin",xp:30},
    {kod:"okuma_2000",ad:"Okuma Efsanesi",ikon:"🌟",kategori:"okuma",seviye:"elmas",xp:50},
    {kod:"streak_3",ad:"İlk Alışkanlık",ikon:"🔥",kategori:"streak",seviye:"bronz",xp:5},
    {kod:"streak_7",ad:"Kararlı Okuyucu",ikon:"💪",kategori:"streak",seviye:"gumus",xp:10},
    {kod:"streak_21",ad:"Demir İrade",ikon:"🏔️",kategori:"streak",seviye:"altin",xp:25},
    {kod:"streak_60",ad:"Durdurulamaz",ikon:"🚀",kategori:"streak",seviye:"elmas",xp:50},
    {kod:"kitap_1",ad:"İlk Kitap",ikon:"📕",kategori:"kitap",seviye:"bronz",xp:5},
    {kod:"kitap_5",ad:"Kitap Kaşifi",ikon:"🗺️",kategori:"kitap",seviye:"gumus",xp:15},
    {kod:"kitap_15",ad:"Kütüphane Dostu",ikon:"📚",kategori:"kitap",seviye:"altin",xp:30},
    {kod:"kitap_30",ad:"Kitap Efsanesi",ikon:"🏰",kategori:"kitap",seviye:"elmas",xp:50},
    {kod:"gorev_ilk",ad:"Görev Başlangıcı",ikon:"✅",kategori:"gorev",seviye:"bronz",xp:5},
    {kod:"gorev_10",ad:"Görev Avcısı",ikon:"🎯",kategori:"gorev",seviye:"gumus",xp:15},
    {kod:"gorev_30",ad:"Görev Ustası",ikon:"🏹",kategori:"gorev",seviye:"altin",xp:30},
    {kod:"gorev_100",ad:"Görev Efsanesi",ikon:"👑",kategori:"gorev",seviye:"elmas",xp:50},
    {kod:"egz_ilk",ad:"Göz Jimnastiği",ikon:"👁️",kategori:"egzersiz",seviye:"bronz",xp:3},
    {kod:"egz_20",ad:"Egzersiz Yıldızı",ikon:"💫",kategori:"egzersiz",seviye:"gumus",xp:10},
    {kod:"egz_14",ad:"Beyin Atleti",ikon:"🧠",kategori:"egzersiz",seviye:"altin",xp:20},
    {kod:"orman_ilk",ad:"İlk Fidan",ikon:"🌱",kategori:"orman",seviye:"bronz",xp:3},
    {kod:"orman_50",ad:"Küçük Orman",ikon:"🌿",kategori:"orman",seviye:"gumus",xp:10},
    {kod:"orman_200",ad:"Orman Korucusu",ikon:"🌳",kategori:"orman",seviye:"altin",xp:25},
    {kod:"lig_gumus",ad:"Gümüş Yolcusu",ikon:"🥈",kategori:"lig",seviye:"gumus",xp:10},
    {kod:"lig_altin",ad:"Altın Savaşçısı",ikon:"🥇",kategori:"lig",seviye:"altin",xp:20},
    {kod:"lig_elmas",ad:"Elmas Efsanesi",ikon:"💎",kategori:"lig",seviye:"elmas",xp:50},
  ]);
  const [anketSorulari, setAnketSorulari] = useState([
    {no:1,soru:"Öğretmenin çocuğunuzla iletişimi nasıl?",tip:"puan",kategori:"iletisim"},
    {no:2,soru:"Görev ve ödevler düzenli veriliyor mu?",tip:"puan",kategori:"duzen"},
    {no:3,soru:"Çocuğunuzun okuma alışkanlığında gelişme görüyor musunuz?",tip:"puan",kategori:"etki"},
    {no:4,soru:"Öğretmen geri bildirimleri yeterli mi?",tip:"puan",kategori:"geri_bildirim"},
    {no:5,soru:"Çocuğunuzun motivasyonu arttı mı?",tip:"puan",kategori:"motivasyon"},
    {no:6,soru:"Öğretmenin egzersiz ve içerik çeşitliliği yeterli mi?",tip:"puan",kategori:"icerik"},
    {no:7,soru:"Genel olarak öğretmenden memnun musunuz?",tip:"puan",kategori:"genel"},
    {no:8,soru:"Bu öğretmeni başka velilere tavsiye eder misiniz?",tip:"evet_hayir",kategori:"tavsiye"},
    {no:9,soru:"Eklemek istediğiniz not (opsiyonel)",tip:"metin",kategori:"not"},
  ]);
  const [kayitEdiliyor, setKayitEdiliyor] = useState(false);

  // DB'de özelleştirilmiş ayar varsa overwrite et
  useEffect(() => {
    const tryLoadFromDB = async () => {
      try { const r = await axios.get(`${API}/ayarlar/xp_tablosu`); if (r.data?.degerler && Object.keys(r.data.degerler).length > 0) setXpTablosu(r.data.degerler); } catch(e) {}
      try { const r = await axios.get(`${API}/ayarlar/lig_esikleri`); if (r.data?.degerler && Object.keys(r.data.degerler).length > 0) setLigEsikleri(r.data.degerler); } catch(e) {}
      try { const r = await axios.get(`${API}/ayarlar/ogretmen_rozetleri`); if (Array.isArray(r.data?.degerler) && r.data.degerler.length > 0) setOgretmenRozetler(r.data.degerler); } catch(e) {}
      try { const r = await axios.get(`${API}/ayarlar/ogrenci_rozetleri`); if (Array.isArray(r.data?.degerler) && r.data.degerler.length > 0) setOgrenciRozetler(r.data.degerler); } catch(e) {}
      try { const r = await axios.get(`${API}/ayarlar/anket_sorulari`); if (Array.isArray(r.data?.degerler) && r.data.degerler.length > 0) setAnketSorulari(r.data.degerler); } catch(e) {}
    };
    tryLoadFromDB();
  }, []);

  const kaydet = async (tip, degerler) => {
    setKayitEdiliyor(true);
    try { await axios.put(`${API}/ayarlar/${tip}`, { degerler }); toast({ title: "✅ Ayarlar kaydedildi!" }); }
    catch(e) { toast({ title: "Hata", variant: "destructive" }); }
    setKayitEdiliyor(false);
  };

  const xpEylemLabel = { okuma_gorevi: "📖 Okuma Görevi", anlama_testi: "📝 Anlama Testi", kelime_gorevi: "🔤 Kelime Görevi", gunluk_streak: "🔥 Günlük Streak", kitap_bitirme: "📚 Kitap Bitirme", yazili_ozet: "✍️ Yazılı Özet", egzersiz: "👁️ Egzersiz", gelisim_tamamla: "🎓 Gelişim Tamamla", gorev_tamamla: "✅ Görev Tamamla" };
  const ligLabel = { bronz: "🥉 Bronz", gumus: "🥈 Gümüş", altin: "🥇 Altın", elmas: "💎 Elmas" };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">⚙️ Sistem Ayarları</h2>
      <p className="text-gray-500 text-sm">Rozet, XP, lig ve anket ayarlarını buradan yönetin. Değişiklikler anında uygulanır.</p>

      <div className="flex gap-2 flex-wrap">
        {[{id:"xp",l:"💰 XP Değerleri"},{id:"lig",l:"🏆 Lig Eşikleri"},{id:"ogretmen_rozet",l:"🏅 Öğretmen Rozetleri"},{id:"ogrenci_rozet",l:"🎓 Öğrenci Rozetleri"},{id:"anket",l:"⭐ Anket Soruları"}].map(s => (
          <button key={s.id} onClick={() => setAyarSekme(s.id)}
            className={`px-4 py-2 rounded-xl text-sm font-medium border transition-all ${ayarSekme === s.id ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-600 border-gray-200'}`}>{s.l}</button>
        ))}
      </div>

      {/* XP Değerleri */}
      {ayarSekme === "xp" && (<Card className="border-0 shadow-sm"><CardHeader><CardTitle>💰 XP Değerleri</CardTitle><p className="text-sm text-gray-500">Her eylem için kazanılan XP miktarı</p></CardHeader><CardContent><div className="space-y-3">
        {Object.entries(xpTablosu).map(([key, val]) => (
          <div key={key} className="flex items-center justify-between gap-4">
            <Label className="text-sm flex-1">{xpEylemLabel[key] || key}</Label>
            <Input type="number" className="w-24 text-center" value={val} onChange={e => setXpTablosu({...xpTablosu, [key]: parseInt(e.target.value) || 0})} />
            <span className="text-xs text-gray-400 w-8">XP</span>
          </div>
        ))}
        <Button onClick={() => kaydet("xp_tablosu", xpTablosu)} disabled={kayitEdiliyor} className="w-full bg-blue-600 text-white mt-4">💾 XP Değerlerini Kaydet</Button>
      </div></CardContent></Card>)}

      {/* Lig Eşikleri */}
      {ayarSekme === "lig" && (<Card className="border-0 shadow-sm"><CardHeader><CardTitle>🏆 Lig Eşikleri</CardTitle><p className="text-sm text-gray-500">Her lig seviyesi için gereken minimum XP</p></CardHeader><CardContent><div className="space-y-3">
        {Object.entries(ligEsikleri).map(([key, val]) => (
          <div key={key} className="flex items-center justify-between gap-4">
            <Label className="text-sm flex-1">{ligLabel[key] || key}</Label>
            <Input type="number" className="w-32 text-center" value={val} onChange={e => setLigEsikleri({...ligEsikleri, [key]: parseInt(e.target.value) || 0})} />
            <span className="text-xs text-gray-400 w-8">XP</span>
          </div>
        ))}
        <Button onClick={() => kaydet("lig_esikleri", ligEsikleri)} disabled={kayitEdiliyor} className="w-full bg-blue-600 text-white mt-4">💾 Lig Eşiklerini Kaydet</Button>
      </div></CardContent></Card>)}

      {/* Öğretmen Rozetleri */}
      {ayarSekme === "ogretmen_rozet" && (<Card className="border-0 shadow-sm"><CardHeader><CardTitle>🏅 Öğretmen Rozetleri ({ogretmenRozetler.length})</CardTitle></CardHeader><CardContent><div className="space-y-3">
        {ogretmenRozetler.map((r, i) => (
          <div key={r.kod} className="bg-gray-50 rounded-xl p-3 space-y-2">
            <div className="flex items-center gap-2"><span className="text-xl">{r.ikon}</span><span className="font-medium text-sm">{r.ad}</span><span className={`text-xs px-2 py-0.5 rounded-full ${r.seviye === "elmas" ? "bg-purple-100 text-purple-700" : r.seviye === "altin" ? "bg-yellow-100 text-yellow-700" : r.seviye === "gumus" ? "bg-gray-100 text-gray-700" : "bg-orange-100 text-orange-700"}`}>{r.seviye}</span><span className="text-xs text-gray-400">{r.kategori}</span></div>
            <div className="grid grid-cols-3 gap-2">
              <div><Label className="text-[10px]">İkon</Label><Input className="text-center" value={r.ikon} onChange={e => { const n = [...ogretmenRozetler]; n[i] = {...n[i], ikon: e.target.value}; setOgretmenRozetler(n); }} /></div>
              <div><Label className="text-[10px]">Puan</Label><Input type="number" value={r.puan} onChange={e => { const n = [...ogretmenRozetler]; n[i] = {...n[i], puan: parseInt(e.target.value) || 0}; setOgretmenRozetler(n); }} /></div>
              <div><Label className="text-[10px]">Seviye</Label><Select value={r.seviye} onValueChange={v => { const n = [...ogretmenRozetler]; n[i] = {...n[i], seviye: v}; setOgretmenRozetler(n); }}><SelectTrigger className="text-xs"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="bronz">Bronz</SelectItem><SelectItem value="gumus">Gümüş</SelectItem><SelectItem value="altin">Altın</SelectItem><SelectItem value="platin">Platin</SelectItem><SelectItem value="elmas">Elmas</SelectItem></SelectContent></Select></div>
            </div>
          </div>
        ))}
        <Button onClick={() => kaydet("ogretmen_rozetleri", ogretmenRozetler)} disabled={kayitEdiliyor} className="w-full bg-blue-600 text-white mt-4">💾 Öğretmen Rozetlerini Kaydet</Button>
      </div></CardContent></Card>)}

      {/* Öğrenci Rozetleri */}
      {ayarSekme === "ogrenci_rozet" && (<Card className="border-0 shadow-sm"><CardHeader><CardTitle>🎓 Öğrenci Rozetleri ({ogrenciRozetler.length})</CardTitle></CardHeader><CardContent><div className="space-y-3">
        {ogrenciRozetler.map((r, i) => (
          <div key={r.kod} className="bg-gray-50 rounded-xl p-3 space-y-2">
            <div className="flex items-center gap-2"><span className="text-xl">{r.ikon}</span><span className="font-medium text-sm">{r.ad}</span><span className="text-xs text-gray-400">{r.kategori}</span></div>
            <div className="grid grid-cols-3 gap-2">
              <div><Label className="text-[10px]">İkon</Label><Input className="text-center" value={r.ikon} onChange={e => { const n = [...ogrenciRozetler]; n[i] = {...n[i], ikon: e.target.value}; setOgrenciRozetler(n); }} /></div>
              <div><Label className="text-[10px]">XP</Label><Input type="number" value={r.xp || 0} onChange={e => { const n = [...ogrenciRozetler]; n[i] = {...n[i], xp: parseInt(e.target.value) || 0}; setOgrenciRozetler(n); }} /></div>
              <div><Label className="text-[10px]">Seviye</Label><Select value={r.seviye} onValueChange={v => { const n = [...ogrenciRozetler]; n[i] = {...n[i], seviye: v}; setOgrenciRozetler(n); }}><SelectTrigger className="text-xs"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="bronz">Bronz</SelectItem><SelectItem value="gumus">Gümüş</SelectItem><SelectItem value="altin">Altın</SelectItem><SelectItem value="elmas">Elmas</SelectItem></SelectContent></Select></div>
            </div>
          </div>
        ))}
        <Button onClick={() => kaydet("ogrenci_rozetleri", ogrenciRozetler)} disabled={kayitEdiliyor} className="w-full bg-blue-600 text-white mt-4">💾 Öğrenci Rozetlerini Kaydet</Button>
      </div></CardContent></Card>)}

      {/* Anket Soruları */}
      {ayarSekme === "anket" && (<Card className="border-0 shadow-sm"><CardHeader><CardTitle>⭐ Veli Anket Soruları ({anketSorulari.length})</CardTitle><p className="text-sm text-gray-500">Velilerin öğretmenleri değerlendirirken göreceği sorular</p></CardHeader><CardContent><div className="space-y-3">
        {anketSorulari.map((s, i) => (
          <div key={i} className="bg-gray-50 rounded-xl p-3 space-y-2">
            <div className="flex items-center gap-2"><span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{s.tip}</span><span className="text-xs text-gray-400">{s.kategori}</span></div>
            <Input value={s.soru} onChange={e => { const n = [...anketSorulari]; n[i] = {...n[i], soru: e.target.value}; setAnketSorulari(n); }} className="text-sm" />
            <div className="grid grid-cols-2 gap-2">
              <div><Label className="text-[10px]">Tip</Label><Select value={s.tip} onValueChange={v => { const n = [...anketSorulari]; n[i] = {...n[i], tip: v}; setAnketSorulari(n); }}><SelectTrigger className="text-xs"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="puan">⭐ Puan (1-5)</SelectItem><SelectItem value="evet_hayir">👍 Evet/Hayır</SelectItem><SelectItem value="metin">📝 Metin</SelectItem></SelectContent></Select></div>
              <div><Label className="text-[10px]">Kategori</Label><Input value={s.kategori} onChange={e => { const n = [...anketSorulari]; n[i] = {...n[i], kategori: e.target.value}; setAnketSorulari(n); }} className="text-xs" /></div>
            </div>
            <Button variant="destructive" size="sm" className="text-xs" onClick={() => setAnketSorulari(anketSorulari.filter((_, j) => j !== i))}>Soru Sil</Button>
          </div>
        ))}
        <Button variant="outline" className="w-full" onClick={() => setAnketSorulari([...anketSorulari, { no: anketSorulari.length + 1, soru: "", tip: "puan", kategori: "genel" }])}><Plus className="h-4 w-4 mr-2" />Yeni Soru Ekle</Button>
        <Button onClick={() => kaydet("anket_sorulari", anketSorulari)} disabled={kayitEdiliyor} className="w-full bg-blue-600 text-white mt-2">💾 Anket Sorularını Kaydet</Button>
      </div></CardContent></Card>)}
    </div>
  );
}

// GÖREV YÖNETİMİ
// ═══════════════════════════════════════════════

function GorevYonetimi({ user, students, teachers }) {
  const { toast } = useToast();
  const [gorevler, setGorevler] = useState([]);
  const [istatistik, setIstatistik] = useState(null);
  const [gorunum, setGorunum] = useState("liste");
  const [seciliHedefler, setSeciliHedefler] = useState([]);
  const [tamamlamaDialogu, setTamamlamaDialogu] = useState(null);
  const [tamamlamaNotu, setTamamlamaNotu] = useState("");
  const [filtre, setFiltre] = useState("hepsi");
  const [hedefTipFiltre, setHedefTipFiltre] = useState("hepsi");
  const [aramaMetni, setAramaMetni] = useState("");

  const [form, setForm] = useState({
    baslik: "", aciklama: "", tur: "ozel", hedef_tip: user.role === "teacher" ? "ogrenci" : "ogretmen",
    son_tarih: "", icerik_id: "",
    makale_link: "", kitap_yazar: "", kitap_isbn: "", kitap_link: "", kitap_kapak: "", film_link: ""
  });
  const [kitapYukleniyor, setKitapYukleniyor] = useState(false);
  const [gelisimIcerikleri, setGelisimIcerikleri] = useState([]);
  const [icerikSecDialogu, setIcerikSecDialogu] = useState(false);

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${API}/gorevler`); setGorevler(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/gorevler/istatistik`); setIstatistik(r.data); } catch(e) {}
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const fetchGelisimIcerikleri = async () => {
    try { const r = await axios.get(`${API}/gelisim/icerik`); const gd = Array.isArray(r.data) ? r.data : []; setGelisimIcerikleri(gd.filter(i => i.durum === "yayinda")); } catch(e) {}
  };

  const turIcon = (tur) => ({ ozel: "📝", film: "🎬", kitap: "📚", makale: "📄", hizmetici: "🎓", egzersiz: "🎯" }[tur] || "📋");
  const turLabelGorev = (tur) => ({ ozel: "Özel Görev", film: "Film", kitap: "Kitap", makale: "Makale", hizmetici: "Hizmetiçi Eğitim", egzersiz: "Egzersiz" }[tur] || tur);
  const turColorGorev = (tur) => ({ ozel: "bg-gray-100 text-gray-600", film: "bg-purple-100 text-purple-600", kitap: "bg-green-100 text-green-600", makale: "bg-orange-100 text-orange-600", hizmetici: "bg-blue-100 text-blue-600", egzersiz: "bg-pink-100 text-pink-600" }[tur] || "bg-gray-100 text-gray-600");
  const durumBadgeGorev = (d) => ({
    bekliyor: <span className="px-2.5 py-1 bg-yellow-100 text-yellow-700 text-xs rounded-full font-medium">⏳ Bekliyor</span>,
    devam_ediyor: <span className="px-2.5 py-1 bg-blue-100 text-blue-700 text-xs rounded-full font-medium">🔄 Devam Ediyor</span>,
    tamamlandi: <span className="px-2.5 py-1 bg-green-100 text-green-700 text-xs rounded-full font-medium">✅ Tamamlandı</span>,
    suresi_doldu: <span className="px-2.5 py-1 bg-red-100 text-red-700 text-xs rounded-full font-medium">⏰ Süresi Doldu</span>,
  }[d] || null);

  const hedefTipBadge = (tip) => tip === "ogretmen"
    ? <span className="px-2 py-0.5 bg-indigo-100 text-indigo-600 text-xs rounded-full font-medium">👩‍🏫 Öğretmen</span>
    : <span className="px-2 py-0.5 bg-emerald-100 text-emerald-600 text-xs rounded-full font-medium">🎓 Öğrenci</span>;

  const resetForm = () => setForm({ baslik: "", aciklama: "", tur: "ozel", hedef_tip: form.hedef_tip, son_tarih: "", icerik_id: "", makale_link: "", kitap_yazar: "", kitap_isbn: "", kitap_link: "", kitap_kapak: "", film_link: "" });

  const gorevOlustur = async (e) => {
    e.preventDefault();
    if (seciliHedefler.length === 0) { toast({ title: "Uyarı", description: "En az bir kişi seçmelisiniz", variant: "destructive" }); return; }
    try {
      if (seciliHedefler.length === 1) {
        await axios.post(`${API}/gorevler`, { ...form, hedef_id: seciliHedefler[0], hedef_tip: form.hedef_tip });
      } else {
        await axios.post(`${API}/gorevler/toplu`, { hedef_idler: seciliHedefler, hedef_tip: form.hedef_tip, gorev: form });
      }
      toast({ title: "✅ Görev atandı", description: `${seciliHedefler.length} kişiye görev oluşturuldu` });
      resetForm(); setSeciliHedefler([]); setGorunum("liste"); fetchAll();
    } catch(e) { toast({ title: "Hata", description: e.response?.data?.detail || "Görev oluşturulamadı", variant: "destructive" }); }
  };

  const durumGuncelle = async (gorevId, yeniDurum, ek = {}) => {
    try {
      await axios.put(`${API}/gorevler/${gorevId}/durum`, { durum: yeniDurum, ...ek });
      toast({ title: yeniDurum === "tamamlandi" ? "✅ Görev tamamlandı!" : "Durum güncellendi" });
      setTamamlamaDialogu(null); setTamamlamaNotu(""); fetchAll();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const gorevSil = async (id) => {
    try { await axios.delete(`${API}/gorevler/${id}`); toast({ title: "Görev silindi" }); fetchAll(); }
    catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const kitapBilgiCekGorev = async (deger, tip) => {
    if (!deger.trim()) return;
    setKitapYukleniyor(true);
    try {
      const r = await axios.post(`${API}/kitap-bilgi-cek`, { deger, tip });
      const d = r.data;
      setForm(prev => ({ ...prev, baslik: d.baslik || prev.baslik, aciklama: d.aciklama || prev.aciklama, kitap_yazar: d.yazar || prev.kitap_yazar, kitap_isbn: d.isbn || prev.kitap_isbn, kitap_kapak: d.kapak_url || prev.kitap_kapak, kitap_link: d.link || prev.kitap_link || deger }));
      toast({ title: "📚 Kitap bilgileri çekildi!" });
    } catch(e) { toast({ title: "Bilgi çekilemedi, manuel girin", variant: "destructive" }); }
    setKitapYukleniyor(false);
  };

  const iceriktenGorev = (icerik) => {
    setForm({ ...form, baslik: icerik.baslik, aciklama: icerik.aciklama, tur: icerik.tur, icerik_id: icerik.id, makale_link: icerik.makale_link || "", kitap_yazar: icerik.kitap_yazar || "", kitap_isbn: icerik.kitap_isbn || "", kitap_link: icerik.kitap_link || "", kitap_kapak: icerik.kitap_kapak || "" });
    setIcerikSecDialogu(false);
    toast({ title: `"${icerik.baslik}" içeriği görev olarak seçildi` });
  };

  const [ogretmenUsers, setOgretmenUsers] = useState([]);
  useEffect(() => {
    if (user.role === "admin" || user.role === "coordinator") {
      axios.get(`${API}/auth/users`).then(r => { const d = Array.isArray(r.data) ? r.data : []; setOgretmenUsers(d.filter(u => u.role === "teacher" || u.role === "coordinator")); }).catch(() => {});
    }
  }, [user.role]);

  const hedefKisiler = form.hedef_tip === "ogretmen"
    ? ogretmenUsers.map(t => ({ id: t.id, ad: `${t.ad || ""} ${t.soyad || ""}`.trim() }))
    : (students || []).filter(s => !s.arsivlendi).map(s => ({ id: s.id, ad: `${s.ad || ""} ${s.soyad || ""}`.trim(), sinif: s.sinif }));

  const toggleHedef = (id) => { setSeciliHedefler(prev => prev.includes(id) ? prev.filter(h => h !== id) : [...prev, id]); };
  const tumunuSec = () => { if (seciliHedefler.length === hedefKisiler.length) setSeciliHedefler([]); else setSeciliHedefler(hedefKisiler.map(h => h.id)); };

  const filtrelenmisGorevler = gorevler.filter(g => {
    if (filtre !== "hepsi" && g.durum !== filtre) return false;
    if (hedefTipFiltre !== "hepsi" && g.hedef_tip !== hedefTipFiltre) return false;
    if (aramaMetni && !g.baslik.toLowerCase().includes(aramaMetni.toLowerCase()) && !g.hedef_ad.toLowerCase().includes(aramaMetni.toLowerCase())) return false;
    return true;
  });

  const benimGorevlerim = gorevler.filter(g => g.hedef_id === user.id);

  // ── TAMAMLAMA DİALOGU ──
  if (tamamlamaDialogu) {
    const g = tamamlamaDialogu;
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => { setTamamlamaDialogu(null); setTamamlamaNotu(""); }}>← Geri</Button>
          <h2 className="text-xl font-bold">Görevi Tamamla</h2>
        </div>
        <Card className="border-0 shadow-sm"><CardHeader><div className="flex items-center gap-2"><span className="text-2xl">{turIcon(g.tur)}</span><CardTitle>{g.baslik}</CardTitle></div>
          {g.aciklama && <p className="text-gray-500 text-sm mt-1">{g.aciklama}</p>}
          {g.kitap_yazar && <p className="text-sm text-gray-500">📚 {g.kitap_yazar}</p>}
          {g.film_link && <a href={g.film_link} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline">🎬 Film Linki</a>}
          {g.makale_link && <a href={g.makale_link} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline">📄 Makale Linki</a>}
        </CardHeader></Card>
        <div><Label>Tamamlama Notu (opsiyonel)</Label><Input value={tamamlamaNotu} onChange={e => setTamamlamaNotu(e.target.value)} placeholder="Ne yaptığınızı kısaca yazın..." /></div>
        <Button onClick={() => durumGuncelle(g.id, "tamamlandi", { not: tamamlamaNotu })}
          className="w-full bg-gradient-to-r from-green-500 to-emerald-600 text-white py-3">
          Görevi Tamamla ✅
        </Button>
      </div>
    );
  }

  // ── GÖREV OLUŞTURMA ──
  if (gorunum === "olustur") {
    return (
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-3 mb-6"><Button variant="outline" size="sm" onClick={() => setGorunum("liste")}>← Geri</Button><h2 className="text-xl font-bold">Yeni Görev Ata</h2></div>
        <form onSubmit={gorevOlustur} className="space-y-6">
          <Card className="border-0 shadow-sm"><CardHeader><CardTitle className="text-base">1. Kime Atanacak?</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {(user.role === "admin" || user.role === "coordinator") && (
                <div className="flex gap-2">
                  <button type="button" onClick={() => { setForm({ ...form, hedef_tip: "ogretmen" }); setSeciliHedefler([]); }}
                    className={`flex-1 py-3 rounded-xl text-sm font-medium transition-all border ${form.hedef_tip === "ogretmen" ? 'bg-indigo-500 text-white border-indigo-500 shadow' : 'bg-white text-gray-600 border-gray-200 hover:border-indigo-300'}`}>
                    👩‍🏫 Öğretmenlere</button>
                  <button type="button" onClick={() => { setForm({ ...form, hedef_tip: "ogrenci" }); setSeciliHedefler([]); }}
                    className={`flex-1 py-3 rounded-xl text-sm font-medium transition-all border ${form.hedef_tip === "ogrenci" ? 'bg-emerald-500 text-white border-emerald-500 shadow' : 'bg-white text-gray-600 border-gray-200 hover:border-emerald-300'}`}>
                    🎓 Öğrencilere</button>
                </div>)}
              <div className="flex items-center justify-between">
                <Label className="text-sm text-gray-500">{seciliHedefler.length} / {hedefKisiler.length} kişi seçildi</Label>
                <button type="button" onClick={tumunuSec} className="text-xs text-blue-600 hover:underline">{seciliHedefler.length === hedefKisiler.length ? "Seçimi Kaldır" : "Tümünü Seç"}</button>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-48 overflow-y-auto p-1">
                {hedefKisiler.map(k => (<button key={k.id} type="button" onClick={() => toggleHedef(k.id)}
                  className={`p-2.5 rounded-xl text-sm text-left transition-all border ${seciliHedefler.includes(k.id) ? 'bg-orange-50 border-orange-400 ring-2 ring-orange-200' : 'bg-white border-gray-200 hover:border-gray-300'}`}>
                  <div className="font-medium truncate">{k.ad}</div>{k.sinif && <div className="text-xs text-gray-400">{k.sinif}. sınıf</div>}</button>))}
              </div>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-sm"><CardHeader><div className="flex items-center justify-between"><CardTitle className="text-base">2. Görev Detayı</CardTitle>
            <button type="button" onClick={() => { fetchGelisimIcerikleri(); setIcerikSecDialogu(true); }} className="text-xs text-blue-600 hover:underline flex items-center gap-1"><BookOpen className="h-3 w-3" /> Mevcut içerikten seç</button></div></CardHeader>
            <CardContent className="space-y-4">
              <div><Label className="mb-2 block">Görev Türü</Label><div className="flex flex-wrap gap-2">
                {[{v:"ozel",l:"📝 Özel Görev"},{v:"hizmetici",l:"🎓 Hizmetiçi"},{v:"film",l:"🎬 Film"},{v:"kitap",l:"📚 Kitap"},{v:"makale",l:"📄 Makale"},{v:"egzersiz",l:"🎯 Egzersiz"}].map(t => (
                  <button key={t.v} type="button" onClick={() => setForm({...form, tur: t.v})}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${form.tur === t.v ? 'bg-orange-500 text-white border-orange-500 shadow' : 'bg-white text-gray-600 border-gray-200 hover:border-orange-300'}`}>{t.l}</button>))}
              </div></div>
              <div><Label>Başlık *</Label><Input value={form.baslik} onChange={e => setForm({...form, baslik: e.target.value})} required placeholder="Görev başlığı..." /></div>
              <div><Label>Açıklama</Label><textarea value={form.aciklama} onChange={e => setForm({...form, aciklama: e.target.value})} placeholder="Detaylı açıklama..." className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm min-h-[80px]" /></div>
              <div><Label>Son Tarih</Label><Input type="date" value={form.son_tarih} onChange={e => setForm({...form, son_tarih: e.target.value})} /></div>

              {form.tur === "film" && (<div className="p-4 bg-purple-50 border border-purple-200 rounded-xl space-y-3"><div className="font-semibold text-sm text-purple-800">🎬 Film Bilgileri</div><div><Label>Film Linki</Label><Input value={form.film_link} onChange={e => setForm({...form, film_link: e.target.value})} placeholder="https://..." /></div></div>)}

              {form.tur === "kitap" && (<div className="p-4 bg-green-50 border border-green-200 rounded-xl space-y-3"><div className="font-semibold text-sm text-green-800">📚 Kitap Bilgileri</div>
                <div className="flex gap-2"><Input placeholder="ISBN veya Barkod" value={form.kitap_isbn} onChange={e => setForm({...form, kitap_isbn: e.target.value})} className="flex-1" />
                  <Button type="button" size="sm" className="bg-green-600 text-white" disabled={kitapYukleniyor || !form.kitap_isbn.trim()} onClick={() => kitapBilgiCekGorev(form.kitap_isbn, 'isbn')}>{kitapYukleniyor ? '⏳' : '🔍'} Ara</Button></div>
                <div className="flex gap-2"><Input placeholder="Kitap sitesi linki" value={form.kitap_link} onChange={e => setForm({...form, kitap_link: e.target.value})} className="flex-1" />
                  <Button type="button" size="sm" className="bg-blue-600 text-white" disabled={kitapYukleniyor || !form.kitap_link.trim()} onClick={() => kitapBilgiCekGorev(form.kitap_link, 'link')}>{kitapYukleniyor ? '⏳' : '🔗'} Çek</Button></div>
                {form.kitap_kapak && <img src={form.kitap_kapak} alt="Kapak" className="h-32 rounded-lg shadow" onError={e => { e.target.style.display='none'; }} />}
                <div><Label>Yazar</Label><Input value={form.kitap_yazar} onChange={e => setForm({...form, kitap_yazar: e.target.value})} /></div></div>)}

              {form.tur === "makale" && (<div className="p-4 bg-orange-50 border border-orange-200 rounded-xl space-y-3"><div className="font-semibold text-sm text-orange-800">📄 Makale Linki</div><Input value={form.makale_link} onChange={e => setForm({...form, makale_link: e.target.value})} placeholder="https://..." /></div>)}
            </CardContent>
          </Card>

          <div className="flex gap-3">
            <Button type="submit" className="flex-1 bg-gradient-to-r from-orange-500 to-red-500 text-white py-3">{seciliHedefler.length > 1 ? `${seciliHedefler.length} Kişiye Görev Ata` : "Görev Ata"}</Button>
            <Button type="button" variant="outline" onClick={() => setGorunum("liste")} className="flex-1">İptal</Button>
          </div>
        </form>

        <Dialog open={icerikSecDialogu} onOpenChange={setIcerikSecDialogu}><DialogContent className="max-w-xl"><DialogHeader><DialogTitle>Mevcut İçerikten Görev Seç</DialogTitle><DialogDescription>Gelişim alanındaki yayında olan içeriklerden birini görev olarak atayabilirsiniz.</DialogDescription></DialogHeader>
          <div className="max-h-96 overflow-y-auto space-y-2">
            {gelisimIcerikleri.length === 0 && <p className="text-gray-500 text-sm text-center py-8">Yayında içerik yok</p>}
            {gelisimIcerikleri.map(ic => (<button key={ic.id} onClick={() => iceriktenGorev(ic)}
              className="w-full text-left p-3 rounded-xl border border-gray-200 hover:border-orange-300 hover:bg-orange-50 transition-all">
              <div className="flex items-center gap-2"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${turColorGorev(ic.tur)}`}>{turIcon(ic.tur)} {turLabelGorev(ic.tur)}</span><span className="font-medium text-sm">{ic.baslik}</span></div>
              {ic.aciklama && <p className="text-xs text-gray-500 mt-1 truncate">{ic.aciklama}</p>}</button>))}
          </div></DialogContent></Dialog>
      </div>
    );
  }

  // ── ANA LİSTE ──
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div><h2 className="text-2xl font-bold text-gray-900">Görev Yönetimi</h2>
          <p className="text-gray-500 text-sm mt-1">{user.role === "teacher" ? "Öğrencilerinize ödev atayın ve görevlerinizi takip edin" : "Öğretmenlere ve öğrencilere görev atayın, takip edin"}</p></div>
        <Button onClick={() => { setGorunum("olustur"); setSeciliHedefler([]); }} className="bg-gradient-to-r from-orange-500 to-red-500 text-white"><Plus className="h-4 w-4 mr-2" /> Yeni Görev Ata</Button>
      </div>

      {istatistik && (<div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[{ label: "Toplam", value: (istatistik.ogretmen?.toplam||0)+(istatistik.ogrenci?.toplam||0), color: "bg-gray-50 text-gray-700", icon: "📋" },
          { label: "Bekliyor", value: (istatistik.ogretmen?.bekliyor||0)+(istatistik.ogrenci?.bekliyor||0), color: "bg-yellow-50 text-yellow-700", icon: "⏳" },
          { label: "Devam Ediyor", value: (istatistik.ogretmen?.devam_ediyor||0)+(istatistik.ogrenci?.devam_ediyor||0), color: "bg-blue-50 text-blue-700", icon: "🔄" },
          { label: "Tamamlandı", value: (istatistik.ogretmen?.tamamlandi||0)+(istatistik.ogrenci?.tamamlandi||0), color: "bg-green-50 text-green-700", icon: "✅" },
          { label: "Süresi Doldu", value: (istatistik.ogretmen?.suresi_doldu||0)+(istatistik.ogrenci?.suresi_doldu||0), color: "bg-red-50 text-red-700", icon: "⏰" },
        ].map((s, i) => (<div key={i} className={`${s.color} rounded-xl p-3 text-center`}><div className="text-2xl font-bold">{s.value}</div><div className="text-xs font-medium">{s.icon} {s.label}</div></div>))}
      </div>)}

      {user.role === "teacher" && benimGorevlerim.filter(g => g.durum !== "tamamlandi").length > 0 && (
        <Card className="border-0 shadow-sm border-l-4 border-l-indigo-500"><CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2">📌 Bana Atanan Görevler <Badge className="bg-indigo-100 text-indigo-700">{benimGorevlerim.filter(g => g.durum !== "tamamlandi").length} aktif</Badge></CardTitle></CardHeader>
          <CardContent><div className="space-y-2">
            {benimGorevlerim.filter(g => g.durum !== "tamamlandi").map(g => (<div key={g.id} className="flex items-center justify-between p-3 bg-indigo-50 rounded-xl">
              <div className="flex items-center gap-3"><span className="text-lg">{turIcon(g.tur)}</span><div><div className="font-medium text-sm">{g.baslik}</div><div className="text-xs text-gray-500">Atayan: {g.atayan_ad} {g.son_tarih && `• Son: ${new Date(g.son_tarih).toLocaleDateString('tr-TR')}`}</div></div></div>
              <div className="flex items-center gap-2">{durumBadgeGorev(g.durum)}
                {g.durum !== "tamamlandi" && (<Button size="sm" className="bg-green-600 text-white text-xs" onClick={() => { setTamamlamaDialogu(g); setTamamlamaNotu(""); }}>Tamamla</Button>)}
              </div></div>))}
          </div></CardContent></Card>)}

      <div className="flex flex-wrap gap-2 items-center">
        <Input placeholder="Görev veya kişi ara..." value={aramaMetni} onChange={e => setAramaMetni(e.target.value)} className="w-64" />
        <div className="flex gap-1">
          {[{v:"hepsi",l:"Hepsi"},{v:"bekliyor",l:"⏳ Bekliyor"},{v:"devam_ediyor",l:"🔄 Devam"},{v:"tamamlandi",l:"✅ Tamamlandı"}].map(f => (
            <button key={f.v} onClick={() => setFiltre(f.v)} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${filtre === f.v ? 'bg-orange-500 text-white border-orange-500' : 'bg-white text-gray-600 border-gray-200 hover:border-orange-300'}`}>{f.l}</button>))}
        </div>
        {(user.role === "admin" || user.role === "coordinator") && (<div className="flex gap-1 ml-2">
          {[{v:"hepsi",l:"Tümü"},{v:"ogretmen",l:"👩‍🏫 Öğretmen"},{v:"ogrenci",l:"🎓 Öğrenci"}].map(f => (
            <button key={f.v} onClick={() => setHedefTipFiltre(f.v)} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${hedefTipFiltre === f.v ? 'bg-blue-500 text-white border-blue-500' : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'}`}>{f.l}</button>))}
        </div>)}
      </div>

      {filtrelenmisGorevler.length === 0 ? (
        <div className="text-center py-16"><div className="text-6xl mb-4">📋</div><h3 className="text-lg font-bold text-gray-900">Henüz görev yok</h3><p className="text-gray-500 text-sm mt-1">Yeni bir görev oluşturarak başlayın.</p></div>
      ) : (<div className="space-y-3">
        {filtrelenmisGorevler.map(g => (
          <Card key={g.id} className={`border-0 shadow-sm transition-all hover:shadow-md ${g.durum === "tamamlandi" ? "opacity-70" : ""}`}><CardContent className="p-4"><div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 flex-1 min-w-0"><span className="text-2xl mt-0.5">{turIcon(g.tur)}</span><div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 flex-wrap"><h4 className="font-bold text-gray-900 truncate">{g.baslik}</h4><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${turColorGorev(g.tur)}`}>{turLabelGorev(g.tur)}</span>{hedefTipBadge(g.hedef_tip)}</div>
              {g.aciklama && <p className="text-gray-500 text-sm mt-1 line-clamp-2">{g.aciklama}</p>}
              <div className="flex items-center gap-3 mt-2 text-xs text-gray-400 flex-wrap">
                <span>📌 {g.hedef_ad}</span><span>🔄 Atayan: {g.atayan_ad}</span>
                {g.son_tarih && <span>📅 Son: {new Date(g.son_tarih).toLocaleDateString('tr-TR')}</span>}
              </div>
              {g.tamamlama_notu && <p className="text-xs text-blue-600 mt-1 italic">💬 "{g.tamamlama_notu}"</p>}
            </div></div>
            <div className="flex items-center gap-2 shrink-0">
              {durumBadgeGorev(g.durum)}
              {g.durum === "bekliyor" && g.hedef_id === user.id && (<Button size="sm" variant="outline" className="text-xs" onClick={() => durumGuncelle(g.id, "devam_ediyor")}>Başla</Button>)}
              {(g.durum === "bekliyor" || g.durum === "devam_ediyor") && g.hedef_id === user.id && (
                <Button size="sm" className="bg-green-600 text-white text-xs" onClick={() => { setTamamlamaDialogu(g); setTamamlamaNotu(""); }}>Tamamla</Button>)}
              {(g.atayan_id === user.id || user.role === "admin") && (<Button size="sm" variant="outline" className="text-xs text-red-500 hover:bg-red-50" onClick={() => gorevSil(g.id)}><Trash2 className="h-3 w-3" /></Button>)}
            </div>
          </div></CardContent></Card>))}
      </div>)}
    </div>
  );
}


// ═══════════════════════════════════════════
// AI MERKEZİ — Admin AI Dashboard
// ═══════════════════════════════════════════
function AiMerkezi({ user }) {
  const { toast } = useToast();
  const [aiSekme, setAiSekme] = useState("genel");
  const [maliyet, setMaliyet] = useState(null);
  const [yuklemeler, setYuklemeler] = useState([]);
  const [kelimeler, setKelimeler] = useState([]);
  const [parcalar, setParcalar] = useState([]);
  const [sorular, setSorular] = useState([]);
  const [dnaListesi, setDnaListesi] = useState([]);
  const [koclukListesi, setKoclukListesi] = useState([]);
  const [socraticListesi, setSocraticListesi] = useState([]);
  const [kelimeTekrar, setKelimeTekrar] = useState([]);
  const [istatistik, setIstatistik] = useState(null);

  useEffect(() => {
    const f = async () => {
      try { const r = await axios.get(`${API}/ai/maliyet-ozet`); setMaliyet(r.data); } catch(e) {}
      try { const r = await axios.get(`${API}/ai/bilgi-tabani/gecmis`); setYuklemeler(Array.isArray(r.data) ? r.data : []); } catch(e) {}
      try { const r = await axios.get(`${API}/ai/bilgi-tabani/istatistik`); setIstatistik(r.data); } catch(e) {}
      try { const r = await axios.get(`${API}/ai/kelime-listesi`); setKelimeler(Array.isArray(r.data) ? r.data : []); } catch(e) {}
      try { const r = await axios.get(`${API}/ai/okuma-parcalari`); setParcalar(Array.isArray(r.data) ? r.data : []); } catch(e) {}
      try { const r = await axios.get(`${API}/ai/sorular`); setSorular(Array.isArray(r.data) ? r.data : []); } catch(e) {}
      try { const r = await axios.get(`${API}/ai/socratic-log`); setSocraticListesi(Array.isArray(r.data) ? r.data : []); } catch(e) {}

      // DNA listesi — her öğrenci için (koçluktan bağımsız)
      try {
        const students = await axios.get(`${API}/students`);
        const slist = Array.isArray(students.data) ? students.data : [];
        const dnaArr = [];
        const kocArr = [];
        // DNA: paralel çek, hızlı
        await Promise.allSettled(slist.slice(0, 30).map(async (s) => {
          try { const dr = await axios.get(`${API}/ai/dna/${s.id}`); dnaArr.push({...dr.data, ad: s.ad, soyad: s.soyad}); } catch(e) {}
        }));
        setDnaListesi([...dnaArr]);
        // Koçluk: API key gerektirir, ayrı try-catch
        await Promise.allSettled(slist.slice(0, 10).map(async (s) => {
          try { const kr = await axios.post(`${API}/ai/kocluk/${s.id}`); kocArr.push({...kr.data, ad: s.ad, soyad: s.soyad}); } catch(e) {}
        }));
        setKoclukListesi([...kocArr]);
      } catch(e) {}
    };
    f();
  }, [user]);

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold flex items-center gap-2">🧠 AI Merkezi</h2>

      {/* Demo Veri Yükle butonu */}
      {user.role === "admin" && (
        <button onClick={async () => {
          try {
            const r = await axios.post(`${API}/ai/demo-yukle`);
            toast({ title: `🎉 ${r.data.mesaj} — DNA: ${r.data.sonuc?.dna}, Koçluk: ${r.data.sonuc?.kocluk}, Kelime: ${r.data.sonuc?.kelime_tekrar}, Soru: ${r.data.sonuc?.soru}` });
            window.location.reload();
          } catch(e) { toast({ title: e.response?.data?.detail || "Hata", variant: "destructive" }); }
        }} className="bg-gradient-to-r from-purple-500 to-pink-500 text-white px-4 py-2 rounded-xl text-sm font-medium shadow hover:shadow-lg transition-all">
          🚀 Demo Verileri Yükle / Yenile
        </button>
      )}

      {/* Sekme butonları */}
      <div className="flex gap-1 flex-wrap">
        {[["genel","📊 Genel"],["dna","🧬 DNA Profilleri"],["kocluk","🤖 Koçluk"],["kelimeler","📚 Kelime Haritası"],["yuklemeler","📁 Yüklemeler"],["socratic","💬 Socratic"],["maliyet","💰 Maliyet"]].map(([k,l]) => (
          <button key={k} onClick={() => setAiSekme(k)} className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${aiSekme === k ? 'bg-cyan-600 text-white shadow' : 'bg-white text-gray-600 border hover:bg-gray-50'}`}>{l}</button>
        ))}
      </div>

      {/* GENEL */}
      {aiSekme === "genel" && (<>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="bg-gradient-to-br from-cyan-500 to-blue-600 rounded-2xl p-4 text-white"><div className="text-3xl font-bold">{istatistik?.toplam_yukleme || yuklemeler.length}</div><div className="text-xs opacity-80">📁 Toplam Yükleme</div></div>
          <div className="bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl p-4 text-white"><div className="text-3xl font-bold">{istatistik?.toplam_kelime || 0}</div><div className="text-xs opacity-80">📚 Toplam Kelime</div></div>
          <div className="bg-gradient-to-br from-purple-500 to-indigo-600 rounded-2xl p-4 text-white"><div className="text-3xl font-bold">{istatistik?.toplam_ai_soru ?? sorular.length ?? 0}</div><div className="text-xs opacity-80">📝 AI Sorusu</div></div>
          <div className="bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl p-4 text-white"><div className="text-3xl font-bold">{dnaListesi.length}</div><div className="text-xs opacity-80">🧬 DNA Profili</div></div>
        </div>
        {maliyet && (
          <div className="bg-white rounded-2xl p-4 border shadow-sm">
            <h3 className="font-bold text-sm mb-3">💰 AI Maliyet Özeti</h3>
            <div className="grid grid-cols-2 gap-4">
              <div><div className="text-xs text-gray-500">Bugün</div><div className="text-lg font-bold text-cyan-600">{maliyet.gunluk?.istek || 0} istek</div><div className="text-sm text-gray-600">${maliyet.gunluk?.maliyet_usd?.toFixed(4) || "0.00"}</div></div>
              <div><div className="text-xs text-gray-500">Bu Ay</div><div className="text-lg font-bold text-blue-600">{maliyet.aylik?.istek || 0} istek</div><div className="text-sm text-gray-600">${maliyet.aylik?.maliyet_usd?.toFixed(4) || "0.00"}</div></div>
            </div>
          </div>
        )}
        {/* Son yüklemeler */}
        <div className="bg-white rounded-2xl p-4 border shadow-sm">
          <h3 className="font-bold text-sm mb-3">📁 Son Yüklemeler</h3>
          <div className="space-y-2">{yuklemeler.slice(0, 5).map(y => (
            <div key={y.id} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
              <div><div className="text-sm font-medium">{y.dosya_format === ".pdf" ? "📕" : "📘"} {y.kitap_adi}</div><div className="text-[10px] text-gray-400">{y.yukleyen_ad} • {y.sinif}. sınıf • {new Date(y.tarih).toLocaleDateString('tr-TR')}</div></div>
              <div className="text-right">
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${y.durum === 'tamamlandi' ? 'bg-green-100 text-green-700' : y.durum === 'hata' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>{y.durum === 'tamamlandi' ? '✅' : y.durum === 'hata' ? '❌' : '⏳'} {y.durum}</span>
                {y.sonuc?.cikarilan_kelime > 0 && <div className="text-[9px] text-gray-400 mt-0.5">{y.sonuc.cikarilan_kelime} kelime • {y.sonuc.uretilen_soru} soru</div>}
              </div>
            </div>
          ))}</div>
        </div>
      </>)}

      {/* DNA PROFİLLERİ */}
      {aiSekme === "dna" && (<>
        <h3 className="font-bold text-sm">🧬 Tüm Öğrenci DNA Profilleri ({dnaListesi.length})</h3>
        <div className="space-y-3">{dnaListesi.map(d => {
          const b = d.boyutlar || {};
          const renk = (v) => v >= 70 ? "bg-green-500" : v >= 40 ? "bg-yellow-500" : "bg-red-500";
          return (
            <div key={d.ogrenci_id} className="bg-white rounded-2xl p-4 border shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2"><span className="font-bold text-sm">{d.ad} {d.soyad}</span><span className="text-xs bg-cyan-100 text-cyan-700 px-2 py-0.5 rounded-full">{d.profil_label}</span></div>
                <span className="text-xs text-gray-400">{d.sinif}. sınıf</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {[["Kelime", b.kelime_gucu, "📚"],["Akıcılık", b.akicilik, "⚡"],["Anlama", b.anlama_derinligi, "🧠"],["Dikkat", b.dikkat_suresi, "🎯"],["Zorluk", b.zorluk_toleransi, "💪"],["Psikoloji", null, "🔮"]].map(([ad, val, ikon]) => (
                  <div key={ad} className="flex items-center gap-1.5">
                    <span className="text-xs">{ikon}</span>
                    <span className="text-[10px] text-gray-500 w-14">{ad}</span>
                    {val !== null ? (<><div className="flex-1 bg-gray-100 rounded-full h-2"><div className={`h-2 rounded-full ${renk(val)}`} style={{width:`${val}%`}} /></div><span className="text-[10px] font-bold w-6 text-right">{val}</span></>) : (
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${b.okuma_psikolojisi === 'keşifçi' ? 'bg-green-100 text-green-700' : b.okuma_psikolojisi === 'kararsız' ? 'bg-red-100 text-red-700' : 'bg-blue-100 text-blue-700'}`}>{b.okuma_psikolojisi || "—"}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          );
        })}</div>
        {dnaListesi.length === 0 && <div className="text-center py-8 text-gray-500">DNA profili henüz oluşturulmamış</div>}
      </>)}

      {/* KOÇLUK */}
      {aiSekme === "kocluk" && (<>
        <h3 className="font-bold text-sm">🤖 AI Koçluk Raporları ({koclukListesi.length})</h3>
        {koclukListesi.length > 0 ? (
          <div className="space-y-3">{koclukListesi.map(k => {
            const a = k.ai_analiz || {};
            return (
              <div key={k.ogrenci_id} className="bg-white rounded-2xl p-4 border shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2"><span className="font-bold text-sm">{k.ad} {k.soyad}</span><span className="text-xs bg-cyan-100 text-cyan-700 px-2 py-0.5 rounded-full">{k.dna?.profil_label || ""}</span></div>
                  <span className="text-xs text-gray-400">{new Date(k.tarih).toLocaleDateString('tr-TR')}</span>
                </div>
                {a.durum_degerlendirmesi ? (<>
                  <div className="text-xs text-green-600 mb-1">✅ {(a.durum_degerlendirmesi.guclu_yonler || []).join(" • ")}</div>
                  <div className="text-xs text-orange-600 mb-1">📈 {(a.durum_degerlendirmesi.gelisim_alanlari || []).join(" • ")}</div>
                  {a.risk_analizi && <div className={`text-xs px-2 py-1 rounded-lg mb-1 ${a.risk_analizi.seviye === 'yüksek' ? 'bg-red-50 text-red-700' : a.risk_analizi.seviye === 'orta' ? 'bg-yellow-50 text-yellow-700' : 'bg-green-50 text-green-700'}`}>🚨 {a.risk_analizi.seviye} — {a.risk_analizi.aciliyet}</div>}
                  {a.kitap_tavsiyeleri && <div className="text-xs text-gray-600">📚 {a.kitap_tavsiyeleri.map(t => t.ad).join(", ")}</div>}
                  {a.motivasyon_mesaji && <div className="text-xs text-cyan-600 mt-1 italic">💬 {a.motivasyon_mesaji}</div>}
                </>) : <div className="text-xs text-gray-400">Rapor bekleniyor...</div>}
              </div>
            );
          })}</div>
        ) : <div className="text-center py-8 text-gray-400">Koçluk raporu yok — önce "Demo Verileri Yükle"</div>}
      </>)}

      {/* KELİME HARİTASI */}
      {aiSekme === "kelimeler" && (<>
        <h3 className="font-bold text-sm">📚 MEB Kelime Haritası ({kelimeler.length} kelime)</h3>
        {istatistik?.sinif_dagilimi && (
          <div className="grid grid-cols-4 gap-2">{Object.entries(istatistik.sinif_dagilimi).filter(([,v]) => v.kelime > 0).map(([s, c]) => (
            <div key={s} className="bg-white rounded-xl p-3 border text-center"><div className="text-lg font-bold text-cyan-600">{c.kelime}</div><div className="text-[10px] text-gray-500">{s}. Sınıf</div></div>
          ))}</div>
        )}
        {istatistik?.top_contributors?.length > 0 && (
          <div className="bg-white rounded-2xl p-4 border shadow-sm">
            <h4 className="font-medium text-sm mb-2">🏆 En Çok Katkı Yapanlar</h4>
            <div className="space-y-1">{istatistik.top_contributors.map((t, i) => (
              <div key={i} className="flex items-center justify-between text-sm"><span>{i === 0 ? "🥇" : i === 1 ? "🥈" : i === 2 ? "🥉" : `${i+1}.`} {t.ad}</span><span className="text-xs text-gray-500">{t.yukleme} dosya • {t.puan} puan</span></div>
            ))}</div>
          </div>
        )}
        {/* Kelime kartları */}
        <div className="space-y-1.5">{kelimeler.map((k, i) => (
          <div key={k.id || i} className="bg-white rounded-lg p-3 border shadow-sm flex items-center justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-bold text-cyan-700">{k.kelime}</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${k.zorluk <= 3 ? 'bg-green-100 text-green-700' : k.zorluk <= 6 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'}`}>{k.zorluk}/10</span>
                <span className="text-[9px] bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-full">{k.sinif}. sınıf</span>
              </div>
              <div className="text-xs text-gray-600 mt-0.5">{k.anlam}</div>
              {k.ornek_cumle && <div className="text-[10px] text-gray-400 italic">"{k.ornek_cumle}"</div>}
            </div>
            <div className="text-[9px] text-gray-400 ml-2">{k.kaynak}</div>
          </div>
        ))}</div>
        {kelimeler.length === 0 && <div className="text-center py-8 text-gray-400">Henüz kelime yok. "Demo Verileri Yükle" butonuna tıklayın.</div>}
      </>)}

      {/* YÜKLEMELER */}
      {aiSekme === "yuklemeler" && (<>
        <h3 className="font-bold text-sm">📁 Tüm Yüklemeler ({yuklemeler.length})</h3>
        <div className="space-y-2">{yuklemeler.map(y => (
          <div key={y.id} className="bg-white rounded-xl p-3 border shadow-sm">
            <div className="flex items-center justify-between">
              <div><div className="text-sm font-medium">{y.dosya_format === ".pdf" ? "📕" : "📘"} {y.kitap_adi}</div><div className="text-[10px] text-gray-400">{y.yukleyen_ad} • {y.sinif}. sınıf • {y.tur} • {(y.dosya_boyut/1024/1024).toFixed(1)} MB</div></div>
              <div className="flex items-center gap-2">
                <span className={`text-[10px] px-2 py-0.5 rounded-full ${y.durum === 'tamamlandi' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>{y.durum}</span>
                {!y.onayli && y.durum !== 'hata' && <button onClick={async () => { try { await axios.put(`${API}/ai/bilgi-tabani/onayla/${y.id}`); toast({ title: "✅ Onaylandı!" }); const r = await axios.get(`${API}/ai/bilgi-tabani/gecmis`); setYuklemeler(Array.isArray(r.data)?r.data:[]); } catch(e) {} }} className="text-xs bg-green-600 text-white px-2 py-1 rounded">Onayla</button>}
              </div>
            </div>
            {y.sonuc && y.sonuc.cikarilan_kelime > 0 && <div className="flex gap-3 mt-1 text-[10px] text-gray-500"><span>📚 {y.sonuc.cikarilan_kelime} kelime</span><span>📖 {y.sonuc.okuma_parcasi} parça</span><span>📝 {y.sonuc.uretilen_soru} soru</span></div>}
          </div>
        ))}</div>
      </>)}

      {/* SOCRATIC */}
      {aiSekme === "socratic" && (<>
        <h3 className="font-bold text-sm">💬 Socratic Reading Geçmişi ({socraticListesi.length})</h3>
        <div className="space-y-2">{socraticListesi.map((s, i) => {
          const bloomRenk = {"bilgi":"bg-blue-100 text-blue-700","kavrama":"bg-green-100 text-green-700","analiz":"bg-orange-100 text-orange-700","sentez":"bg-red-100 text-red-700","degerlendirme":"bg-purple-100 text-purple-700"};
          return (
            <div key={s.id || i} className="bg-white rounded-xl p-3 border shadow-sm">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium">{s.ogrenci_ad}</span>
                <div className="flex items-center gap-2">
                  <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${bloomRenk[s.bloom] || 'bg-gray-100'}`}>{s.bloom}</span>
                  {s.puan && <span className="text-xs text-yellow-600">{"⭐".repeat(s.puan)}</span>}
                </div>
              </div>
              <p className="text-xs text-gray-700">❓ {s.soru}</p>
              <div className="flex items-center justify-between mt-1">
                <span className="text-[10px] text-gray-400">📖 {s.kitap_adi} • {s.bolum}</span>
                <span className="text-[10px] text-gray-400">{new Date(s.tarih).toLocaleDateString('tr-TR')}</span>
              </div>
            </div>
          );
        })}</div>
        {socraticListesi.length === 0 && <div className="text-center py-8 text-gray-400">Henüz Socratic log yok. "Demo Verileri Yükle" butonuna tıklayın.</div>}
      </>)}

      {/* MALİYET */}
      {aiSekme === "maliyet" && (<>
        <h3 className="font-bold text-sm">💰 AI Maliyet Detayı</h3>
        {maliyet ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white rounded-2xl p-4 border shadow-sm"><div className="text-xs text-gray-500 mb-1">📅 Bugünkü Harcama</div><div className="text-2xl font-bold text-cyan-600">${maliyet.gunluk?.maliyet_usd?.toFixed(4) || "0.00"}</div><div className="text-sm text-gray-600">{maliyet.gunluk?.istek || 0} API isteği</div></div>
              <div className="bg-white rounded-2xl p-4 border shadow-sm"><div className="text-xs text-gray-500 mb-1">📆 Bu Ay</div><div className="text-2xl font-bold text-blue-600">${maliyet.aylik?.maliyet_usd?.toFixed(4) || "0.00"}</div><div className="text-sm text-gray-600">{maliyet.aylik?.istek || 0} API isteği</div></div>
            </div>
            <div className="bg-white rounded-2xl p-4 border shadow-sm">
              <div className="text-xs text-gray-500 mb-2">Günlük Limit</div>
              <div className="flex items-center gap-2"><div className="flex-1 bg-gray-100 rounded-full h-3"><div className="h-3 bg-cyan-500 rounded-full" style={{width:`${Math.min(100, (maliyet.gunluk?.istek||0)/maliyet.gunluk_limit*100)}%`}} /></div><span className="text-sm font-bold">{maliyet.gunluk?.istek || 0}/{maliyet.gunluk_limit}</span></div>
            </div>
          </div>
        ) : <div className="text-center py-8 text-gray-400">Maliyet verisi yükleniyor...</div>}
      </>)}
    </div>
  );
}


function GelisimAlani({ user, students = [], teachers = [], courses = [], onTabChange }) {
  const { toast } = useToast();
  const [icerikler, setIcerikler] = useState([]);
  const [tamamlananlar, setTamamlananlar] = useState([]);
  const [puanTablosu, setPuanTablosu] = useState([]);
  const [aktifIcerik, setAktifIcerik] = useState(null);
  const [gorunum, setGorunum] = useState("liste");
  const [testCevaplari, setTestCevaplari] = useState([]);
  const [sonuc, setSonuc] = useState(null);
  const [redSebep, setRedSebep] = useState("");
  const [acikDetayId, setAcikDetayId] = useState(null);
  const [redDialogIcerik, setRedDialogIcerik] = useState(null);
  // Bölüm bazlı soru yönetimi
  const [soruYonetimiIcerik, setSoruYonetimiIcerik] = useState(null);
  const [kitapSorulari, setKitapSorulari] = useState([]);
  const [soruForm, setSoruForm] = useState({ bolum: 1, soru: "", secenekler: ["", "", "", ""], dogru_cevap: 0, taksonomi: "kavrama" });
  // AI Bilgi Tabanı state'leri
  const [aiYuklemeler, setAiYuklemeler] = useState([]);
  const [aiStat, setAiStat] = useState(null);
  const [aiPuanlar, setAiPuanlar] = useState({ toplam: 0, detay: [] });
  const [yukleForm, setYukleForm] = useState({ sinif: "3", tur: "ders_kitabi", kitap_adi: "", yazar: "", temalar: "" });
  const [aiBilgiYukleniyor, setAiBilgiYukleniyor] = useState(false);
  const dosyaRef = React.useRef(null);
  // AI işleme state'leri
  const [aiIlerleme, setAiIlerleme] = useState(0);
  const [aiIslemDurum, setAiIslemDurum] = useState("");
  const [aiSonuc, setAiSonuc] = useState(null);
  const [aiSonucSekme, setAiSonucSekme] = useState("kelimeler");
  const [adminForm, setAdminForm] = useState({ baslik: "", tur: "hizmetici", aciklama: "", hedef_kitle: "hepsi", sorular: [], makale_link: "", makale_dosya_turu: "link", kitap_yazar: "", kitap_isbn: "", kitap_yayinevi: "", kitap_sayfa: "", kitap_yas_grubu: "", kitap_link: "", kitap_kapak: "" });
  const [kitapYukleniyor, setKitapYukleniyor] = useState(false);
  const [yeniSoru, setYeniSoru] = useState({ soru: "", secenekler: ["", "", "", ""], dogru_cevap: 0, taksonomi: "kavrama" });
  const [gelisimSekme, setGelisimSekme] = useState("icerikler");
  const [egzersizPuanlari, setEgzersizPuanlari] = useState({});

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${API}/gelisim/icerik`); setIcerikler(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/gelisim/tamamlama/${user.id}`); setTamamlananlar(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/puan-tablosu/birlesik`); setPuanTablosu(Array.isArray(r.data) ? r.data : []); } catch(e) {}
    try { const r = await axios.get(`${API}/egzersiz/puanlar`); setEgzersizPuanlari(r.data); } catch(e) {}
  }, [user.id]);

  useEffect(() => { fetchAll(); }, [fetchAll]);
  // AI Bilgi Tabanı verilerini yükle
  useEffect(() => { const f = async () => { try { const r = await axios.get(`${API}/ai/bilgi-tabani/gecmis`); setAiYuklemeler(Array.isArray(r.data)?r.data:[]); } catch(e) {} try { const r = await axios.get(`${API}/ai/bilgi-tabani/istatistik`); setAiStat(r.data); } catch(e) {} try { const r = await axios.get(`${API}/ai/bilgi-tabani/puanlarim`); setAiPuanlar(r.data); } catch(e) {} }; f(); }, [user]);

  const turIcon = (tur) => ({ hizmetici: <GraduationCap className="h-5 w-5"/>, film: <Film className="h-5 w-5"/>, kitap: <BookMarked className="h-5 w-5"/>, makale: <FileText className="h-5 w-5"/> }[tur] || <BookOpen className="h-5 w-5"/>);
  const turLabel = (tur) => ({ hizmetici: "Hizmetiçi Eğitim", film: "Film", kitap: "Kitap", makale: "Makale" }[tur] || tur);
  const turColor = (tur) => ({ hizmetici: "bg-blue-100 text-blue-600", film: "bg-purple-100 text-purple-600", kitap: "bg-green-100 text-green-600", makale: "bg-orange-100 text-orange-600" }[tur] || "bg-gray-100 text-gray-600");
  const durumBadge = (d) => ({
    beklemede: <span className="px-2 py-1 bg-yellow-100 text-yellow-700 text-xs rounded-full font-medium">⏳ Yönetici Onayı Bekliyor</span>,
    oylama: <span className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded-full font-medium">🗳️ Öğretmen Oylamasında</span>,
    yayinda: <span className="px-2 py-1 bg-green-100 text-green-700 text-xs rounded-full font-medium">✅ Yayında</span>,
    reddedildi: <span className="px-2 py-1 bg-red-100 text-red-700 text-xs rounded-full font-medium">❌ Reddedildi</span>,
  }[d] || null);

  const isTamamlandi = (id) => tamamlananlar.some(t => t.icerik_id === id);
  const getPuan = (id) => { const t = tamamlananlar.find(t => t.icerik_id === id); return t ? t.kazanilan_puan : null; };
  const oyKullandi = (icerik) => icerik.oylar && icerik.oylar[user.id];
  const onayOrani = (icerik) => {
    const oylar = icerik.oylar || {};
    const toplam = Object.keys(oylar).length;
    if (toplam === 0) return null;
    const onay = Object.values(oylar).filter(o => o.onay).length;
    return Math.round(onay / toplam * 100);
  };

  const adminKarar = async (icerikId, onay, direkt = false) => {
    try {
      await axios.post(`${API}/gelisim/icerik/${icerikId}/admin-karar`, { onay, direkt });
      toast({ title: direkt ? "✅ Direkt yayına alındı" : onay ? "🗳️ Oylama başlatıldı" : "❌ İçerik reddedildi" });
      fetchAll();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const oyVer = async (onay, sebep = "", icerikObj = null) => {
    const hedef = icerikObj || aktifIcerik || redDialogIcerik;
    if (!onay && !sebep) { setRedDialogIcerik(hedef); return; }
    try {
      const r = await axios.post(`${API}/gelisim/oy`, { icerik_id: hedef.id, onay, sebep });
      toast({ title: onay ? `✅ Onaylandı (+2 puan)` : "❌ Reddedildi", description: `Onay oranı: %${r.data.onay_orani}` });
      setRedDialogIcerik(null); setRedSebep(""); fetchAll();
    } catch(e) { console.error('Session error:', e.response?.data); toast({ title: "Hata", description: e.response?.data?.detail || "Hata", variant: "destructive" }); }
  };

  const handleTamamla = async (testYapildi, icerikParam = null) => {
    const hedef = icerikParam || aktifIcerik;
    if (!hedef) { toast({ title: "İçerik seçilmedi", variant: "destructive" }); return; }
    try {
      const data = { icerik_id: hedef.id, kullanici_id: user.id };
      if (testYapildi) data.test_cevaplari = testCevaplari;
      const r = await axios.post(`${API}/gelisim/tamamla`, data);
      setSonuc(r.data); setGorunum("sonuc"); fetchAll();
      toast({ title: `+${r.data.puan} puan kazandınız!` });
    } catch(e) { console.error('Session error:', e.response?.data); toast({ title: "Hata", description: e.response?.data?.detail, variant: "destructive" }); }
  };

  const soruEkle = () => {
    if (!yeniSoru.soru || yeniSoru.secenekler.some(s => !s)) {
      toast({ title: "Uyarı", description: "Soru ve tüm seçenekler dolu olmalı", variant: "destructive" }); return;
    }
    setAdminForm({ ...adminForm, sorular: [...adminForm.sorular, { ...yeniSoru, id: Date.now().toString() }] });
    setYeniSoru({ soru: "", secenekler: ["", "", "", ""], dogru_cevap: 0, taksonomi: "kavrama" });
  };

  const kitapBilgiCek = async (deger, tip) => {
    // tip: 'isbn', 'link'
    if (!deger.trim()) return;
    setKitapYukleniyor(true);
    try {
      const r = await axios.post(`${API}/kitap-bilgi-cek`, { deger, tip });
      const d = r.data;
      setAdminForm(prev => ({
        ...prev,
        baslik: d.baslik || prev.baslik,
        aciklama: d.aciklama || prev.aciklama,
        kitap_yazar: d.yazar || prev.kitap_yazar,
        kitap_isbn: d.isbn || prev.kitap_isbn,
        kitap_yayinevi: d.yayinevi || prev.kitap_yayinevi,
        kitap_sayfa: d.sayfa_sayisi || prev.kitap_sayfa,
        kitap_kapak: d.kapak_url || prev.kitap_kapak,
        kitap_link: d.link || prev.kitap_link || deger,
      }));
      toast({ title: "📚 Kitap bilgileri çekildi!" });
    } catch(e) {
      toast({ title: "Bilgi çekilemedi, manuel girin", variant: "destructive" });
    }
    setKitapYukleniyor(false);
  };

  const icerikKaydet = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/gelisim/icerik`, adminForm);
      setAdminForm({ baslik: "", tur: "hizmetici", aciklama: "", hedef_kitle: "hepsi", sorular: [], makale_link: "", makale_dosya_turu: "link", kitap_yazar: "", kitap_isbn: "", kitap_yayinevi: "", kitap_sayfa: "", kitap_yas_grubu: "", kitap_link: "", kitap_kapak: "" });
      setGorunum("liste"); fetchAll();
      toast({ title: (user.role === "admin" || user.role === "coordinator") ? "İçerik oylama aşamasına alındı" : "İçerik yönetici onayına gönderildi" });
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  // ── TEST GÖRÜNÜMÜ ──
  // ── BÖLÜM BAZLI SORU YÖNETİMİ ──
  if (gorunum === "soru-yonetimi" && soruYonetimiIcerik) {
    const bolumSayisi = soruYonetimiIcerik.kitap_bolum_sayisi || 10;
    const bolumler = Array.from({ length: bolumSayisi }, (_, i) => i + 1);

    const soruEkle = async (e) => {
      e.preventDefault();
      if (soruForm.secenekler.some(s => !s.trim())) { toast({ title: "Tüm şıkları doldurun", variant: "destructive" }); return; }
      try {
        await axios.post(`${API}/kitaplar/${soruYonetimiIcerik.id}/sorular`, soruForm);
        toast({ title: "✅ Soru eklendi!" });
        setSoruForm({ bolum: soruForm.bolum, soru: "", secenekler: ["", "", "", ""], dogru_cevap: 0, taksonomi: soruForm.taksonomi });
        const r = await axios.get(`${API}/kitaplar/${soruYonetimiIcerik.id}/sorular`);
        setKitapSorulari(Array.isArray(r.data) ? r.data : []);
      } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
    };

    const soruSil = async (id) => {
      try { await axios.delete(`${API}/kitaplar/sorular/${id}`);
        const r = await axios.get(`${API}/kitaplar/${soruYonetimiIcerik.id}/sorular`);
        setKitapSorulari(Array.isArray(r.data) ? r.data : []); toast({ title: "Silindi" });
      } catch(e) {}
    };

    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => { setGorunum("liste"); setSoruYonetimiIcerik(null); }}>← Geri</Button>
          <div><h2 className="text-lg font-bold">📝 {soruYonetimiIcerik.baslik}</h2>
            <p className="text-xs text-gray-500">{soruYonetimiIcerik.kitap_yazar} • {bolumSayisi} bölüm • {kitapSorulari.length} soru</p></div>
        </div>

        {/* Soru ekleme formu */}
        <Card className="border-0 shadow-sm border-l-4 border-l-teal-500">
          <CardHeader className="pb-2"><CardTitle className="text-sm">📝 Yeni Soru Ekle</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={soruEkle} className="space-y-3">
              <div className="grid grid-cols-3 gap-3">
                <div><Label className="text-xs">Bölüm</Label>
                  <Select value={String(soruForm.bolum)} onValueChange={v => setSoruForm({...soruForm, bolum: parseInt(v)})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{bolumler.map(b => <SelectItem key={b} value={String(b)}>Bölüm {b}</SelectItem>)}</SelectContent>
                  </Select></div>
                <div><Label className="text-xs">Bloom Basamağı</Label>
                  <Select value={soruForm.taksonomi} onValueChange={v => setSoruForm({...soruForm, taksonomi: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="bilgi">1️⃣ Bilgi (Hatırlama)</SelectItem>
                      <SelectItem value="kavrama">2️⃣ Kavrama (Anlama)</SelectItem>
                      <SelectItem value="uygulama">3️⃣ Uygulama</SelectItem>
                      <SelectItem value="analiz">4️⃣ Analiz</SelectItem>
                      <SelectItem value="sentez">5️⃣ Sentez (Değerlendirme)</SelectItem>
                      <SelectItem value="degerlendirme">6️⃣ Yaratma</SelectItem>
                    </SelectContent>
                  </Select></div>
                <div><Label className="text-xs">Doğru Cevap</Label>
                  <Select value={String(soruForm.dogru_cevap)} onValueChange={v => setSoruForm({...soruForm, dogru_cevap: parseInt(v)})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{["A","B","C","D"].map((s,i) => <SelectItem key={i} value={String(i)}>{s}</SelectItem>)}</SelectContent>
                  </Select></div>
              </div>

              {/* Bloom Taksonomisi ipucu */}
              <div className={`rounded-xl p-3 text-xs border ${
                soruForm.taksonomi === "bilgi" ? "bg-blue-50 border-blue-200" :
                soruForm.taksonomi === "kavrama" ? "bg-green-50 border-green-200" :
                soruForm.taksonomi === "uygulama" ? "bg-yellow-50 border-yellow-200" :
                soruForm.taksonomi === "analiz" ? "bg-orange-50 border-orange-200" :
                soruForm.taksonomi === "sentez" ? "bg-red-50 border-red-200" :
                "bg-purple-50 border-purple-200"
              }`}>
                {soruForm.taksonomi === "bilgi" && (<><span className="font-bold text-blue-700">1️⃣ Bilgi (Hatırlama):</span> Metinde doğrudan geçen bilgiyi sorun. <span className="text-gray-500 italic">Örnek kalıplar: "Kim?", "Ne zaman?", "Nerede?", "Adı neydi?", "Hangisi metinde geçmiştir?"</span></>)}
                {soruForm.taksonomi === "kavrama" && (<><span className="font-bold text-green-700">2️⃣ Kavrama (Anlama):</span> Bilgiyi kendi cümleleriyle ifade etmesini isteyin. <span className="text-gray-500 italic">Örnek kalıplar: "Ne anlatılmak istenmiştir?", "Özetleyiniz", "Hangi anlama gelir?", "Ana fikir nedir?"</span></>)}
                {soruForm.taksonomi === "uygulama" && (<><span className="font-bold text-yellow-700">3️⃣ Uygulama:</span> Öğrenileni farklı bir durumda kullanmasını isteyin. <span className="text-gray-500 italic">Örnek kalıplar: "Sen olsaydın ne yapardın?", "Bu bilgiyi nerede kullanabilirsin?", "Başka bir örnek ver"</span></>)}
                {soruForm.taksonomi === "analiz" && (<><span className="font-bold text-orange-700">4️⃣ Analiz:</span> Parçalara ayırma, neden-sonuç, karşılaştırma sorun. <span className="text-gray-500 italic">Örnek kalıplar: "Neden böyle davrandı?", "Aradaki fark nedir?", "Hangi kanıt destekler?", "Sebebi ne olabilir?"</span></>)}
                {soruForm.taksonomi === "sentez" && (<><span className="font-bold text-red-700">5️⃣ Sentez (Değerlendirme):</span> Yargılama, görüş bildirme, savunma isteyin. <span className="text-gray-500 italic">Örnek kalıplar: "Katılıyor musun? Neden?", "Doğru mu yanlış mı? Gerekçele", "En önemli mesaj nedir?"</span></>)}
                {soruForm.taksonomi === "degerlendirme" && (<><span className="font-bold text-purple-700">6️⃣ Yaratma:</span> Yeni bir şey üretme, tasarlama, tahmin etme. <span className="text-gray-500 italic">Örnek kalıplar: "Farklı bir son yaz", "Başlık öner", "Devamını tahmin et", "Yeni bir karakter ekle"</span></>)}
              </div>

              <div><Label className="text-xs">Soru</Label><Input value={soruForm.soru} onChange={e => setSoruForm({...soruForm, soru: e.target.value})} required placeholder={
                soruForm.taksonomi === "bilgi" ? "Metinde ... kim / ne zaman / nerede?" :
                soruForm.taksonomi === "kavrama" ? "Bu bölümde anlatılmak istenen nedir?" :
                soruForm.taksonomi === "uygulama" ? "Sen olsaydın bu durumda ne yapardın?" :
                soruForm.taksonomi === "analiz" ? "Karakterin böyle davranmasının sebebi nedir?" :
                soruForm.taksonomi === "sentez" ? "Bu karara katılıyor musun? Neden?" :
                "Hikayenin farklı bir sonunu tasarla"
              } /></div>
              <div className="grid grid-cols-2 gap-2">
                {["A","B","C","D"].map((s,i) => (
                  <div key={i}><Label className="text-xs">{s})</Label>
                    <Input value={soruForm.secenekler[i]} onChange={e => { const n = [...soruForm.secenekler]; n[i] = e.target.value; setSoruForm({...soruForm, secenekler: n}); }}
                      required placeholder={`${s} şıkkı`} className={soruForm.dogru_cevap === i ? "border-green-500 bg-green-50" : ""} /></div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Button type="submit" className="bg-teal-600 text-white">Soru Ekle</Button>
                <Button type="button" className="bg-gradient-to-r from-cyan-500 to-blue-600 text-white" onClick={async () => {
                  if (!soruYonetimiIcerik?.baslik) { toast({ title: "Kitap seçili değil", variant: "destructive" }); return; }
                  toast({ title: "🤖 AI soru üretiyor..." });
                  try {
                    const r = await axios.post(`${API}/ai/soru-uret`, { metin: `Kitap: ${soruYonetimiIcerik.baslik}. Bölüm ${soruForm.bolum}. Sınıf: ${soruYonetimiIcerik.kitap_yas_grubu || "3-4"}. Tema: ${soruYonetimiIcerik.baslik}`, sinif: parseInt(soruYonetimiIcerik.kitap_yas_grubu) || 4, soru_sayisi: 5 });
                    const sorularAI = r.data?.sorular || [];
                    for (const s of sorularAI) {
                      await axios.post(`${API}/kitaplar/${soruYonetimiIcerik.id}/sorular`, { bolum: soruForm.bolum, soru: s.soru, secenekler: s.secenekler, dogru_cevap: s.dogru_cevap, taksonomi: s.taksonomi || "kavrama" });
                    }
                    toast({ title: `🤖 ${sorularAI.length} soru AI tarafından eklendi!` });
                    const rr = await axios.get(`${API}/kitaplar/${soruYonetimiIcerik.id}/sorular`); setKitapSorulari(Array.isArray(rr.data) ? rr.data : []);
                  } catch(e) { toast({ title: "AI soru üretilemedi", variant: "destructive" }); }
                }}>🤖 AI ile Üret</Button>
              </div>
            </form>
          </CardContent>
        </Card>

        {/* Mevcut sorular bölüm bazlı */}
        {bolumler.map(b => {
          const bolumSorulari = kitapSorulari.filter(s => s.bolum === b);
          if (bolumSorulari.length === 0) return null;
          return (<div key={b}>
            <h3 className="font-medium text-sm text-gray-700 mt-3 mb-2">Bölüm {b} ({bolumSorulari.length} soru)</h3>
            {bolumSorulari.map((s, i) => {
              const taksLabel = {"bilgi":"1️⃣ Bilgi","kavrama":"2️⃣ Kavrama","uygulama":"3️⃣ Uygulama","analiz":"4️⃣ Analiz","sentez":"5️⃣ Sentez","degerlendirme":"6️⃣ Yaratma"};
              const taksRenk = {"bilgi":"bg-blue-100 text-blue-700","kavrama":"bg-green-100 text-green-700","uygulama":"bg-yellow-100 text-yellow-700","analiz":"bg-orange-100 text-orange-700","sentez":"bg-red-100 text-red-700","degerlendirme":"bg-purple-100 text-purple-700"};
              return (
              <div key={s.id} className="bg-white rounded-xl p-3 shadow-sm border mb-2">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-medium text-sm">{i+1}. {s.soru}</span>
                    </div>
                    {s.taksonomi && <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${taksRenk[s.taksonomi] || "bg-gray-100 text-gray-600"}`}>{taksLabel[s.taksonomi] || s.taksonomi}</span>}
                    <div className="grid grid-cols-2 gap-1 mt-1 ml-3">
                      {(s.secenekler || []).map((sec, j) => (
                        <div key={j} className={`text-xs px-2 py-0.5 rounded ${j === s.dogru_cevap ? 'bg-green-100 text-green-700 font-bold' : 'text-gray-500'}`}>
                          {["A","B","C","D"][j]}) {sec}
                        </div>
                      ))}
                    </div>
                  </div>
                  <Button variant="destructive" size="sm" className="text-xs h-6" onClick={() => soruSil(s.id)}>Sil</Button>
                </div>
              </div>
              );
            })}
          </div>);
        })}

        {kitapSorulari.length === 0 && <div className="text-center py-8 text-gray-400">Henüz soru eklenmedi. Yukarıdaki formdan soru ekleyin.</div>}
      </div>
    );
  }

  if (gorunum === "test" && aktifIcerik) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => { setGorunum("liste"); setTestCevaplari([]); }}>← Geri</Button>
          <h2 className="text-xl font-bold">{aktifIcerik.baslik} — Test</h2>
        </div>
        {aktifIcerik.sorular.map((soru, i) => (
          <Card key={i} className="border-0 shadow-sm">
            <CardContent className="p-6">
              <p className="font-medium mb-4">{i + 1}. {soru.soru}</p>
              <div className="space-y-2">
                {soru.secenekler.map((s, j) => (
                  <button key={j} onClick={() => { const c=[...testCevaplari]; c[i]=j; setTestCevaplari(c); }}
                    className={`w-full text-left p-3 rounded-xl border-2 transition-all ${testCevaplari[i]===j ? 'border-orange-500 bg-orange-50' : 'border-gray-200 hover:border-gray-300'}`}>
                    <span className="font-medium mr-2">{['A','B','C','D'][j]})</span>{s}
                  </button>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
        <Button onClick={() => handleTamamla(true)}
          disabled={testCevaplari.filter(c => c !== undefined).length < aktifIcerik.sorular.length}
          className="w-full bg-gradient-to-r from-orange-500 to-red-500 text-white py-3">
          Testi Tamamla ({testCevaplari.filter(c=>c!==undefined).length} / {aktifIcerik.sorular.length} cevaplandı)
        </Button>
      </div>
    );
  }

  // ── SONUÇ GÖRÜNÜMÜ ──
  if (gorunum === "sonuc" && sonuc) {
    return (
      <div className="max-w-md mx-auto text-center space-y-6 py-12">
        <div className="w-24 h-24 bg-gradient-to-br from-yellow-400 to-orange-500 rounded-full flex items-center justify-center mx-auto">
          <Trophy className="h-12 w-12 text-white" />
        </div>
        <div>
          <h2 className="text-4xl font-bold text-gray-900">+{sonuc.puan} Puan!</h2>
          {sonuc.test_yapildi
            ? <p className="text-gray-600 mt-2 text-lg">{sonuc.dogru} / {sonuc.toplam} doğru cevap</p>
            : <p className="text-gray-500 mt-2">Test çözülmeden tamamlandı</p>}
        </div>
        <Button onClick={() => { setGorunum("liste"); setSonuc(null); setAktifIcerik(null); }}
          className="bg-gradient-to-r from-orange-500 to-red-500 text-white px-8">
          Listeye Dön
        </Button>
      </div>
    );
  }

  // ── İÇERİK EKLEME GÖRÜNÜMÜ ──
  if (gorunum === "icerikEkle") {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Button variant="outline" size="sm" onClick={() => setGorunum("liste")}>← Geri</Button>
          <h2 className="text-xl font-bold">Yeni İçerik Ekle</h2>
        </div>
        <Card className="border-0 shadow-sm">
          <CardContent className="p-6">
            <form onSubmit={icerikKaydet} className="space-y-5">
              <div><Label>Başlık *</Label><Input value={adminForm.baslik} onChange={e => setAdminForm({...adminForm, baslik: e.target.value})} required /></div>

              {/* Tür - Buton Grubu */}
              <div>
                <Label className="mb-2 block">Tür</Label>
                <div className="flex flex-wrap gap-2">
                  {[{v:"hizmetici",l:"🎓 Hizmetiçi Eğitim"},{v:"film",l:"🎬 Film"},{v:"kitap",l:"📚 Kitap"},{v:"makale",l:"📄 Makale"}].map(t => (
                    <button key={t.v} type="button" onClick={() => setAdminForm({...adminForm, tur: t.v})}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${adminForm.tur === t.v ? 'bg-orange-500 text-white border-orange-500 shadow-md' : 'bg-white text-gray-600 border-gray-200 hover:border-orange-300 hover:bg-orange-50'}`}>
                      {t.l}
                    </button>
                  ))}
                </div>
              </div>

              {/* Hedef Kitle - Buton Grubu */}
              <div>
                <Label className="mb-2 block">Hedef Kitle</Label>
                <div className="flex flex-wrap gap-2">
                  {[{v:"hepsi",l:"👥 Herkes"},{v:"ogretmen",l:"👩‍🏫 Öğretmenler"},{v:"ogrenci",l:"🎓 Öğrenciler"}].map(t => (
                    <button key={t.v} type="button" onClick={() => setAdminForm({...adminForm, hedef_kitle: t.v})}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-all border ${adminForm.hedef_kitle === t.v ? 'bg-blue-500 text-white border-blue-500 shadow-md' : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300 hover:bg-blue-50'}`}>
                      {t.l}
                    </button>
                  ))}
                </div>
              </div>

              <div><Label>Açıklama</Label><Input value={adminForm.aciklama} onChange={e => setAdminForm({...adminForm, aciklama: e.target.value})} placeholder="Kısa açıklama..." /></div>

              {/* Makale alanları */}
              {adminForm.tur === "makale" && (
                <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl space-y-3">
                  <div className="font-semibold text-sm text-blue-800">📎 Makale Kaynağı</div>
                  <div>
                    <Label className="mb-2 block">Dosya Türü</Label>
                    <div className="flex gap-2">
                      {[{v:"link",l:"🔗 Web Linki"},{v:"pdf",l:"📕 PDF"},{v:"word",l:"📘 Word"}].map(t => (
                        <button key={t.v} type="button" onClick={() => setAdminForm({...adminForm, makale_dosya_turu: t.v})}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${(adminForm.makale_dosya_turu || "link") === t.v ? 'bg-blue-500 text-white border-blue-500' : 'bg-white text-gray-600 border-gray-200 hover:border-blue-300'}`}>
                          {t.l}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <Label>{(adminForm.makale_dosya_turu || "link") === "link" ? "URL" : "Paylaşım Linki (Drive/Dropbox)"}</Label>
                    <Input value={adminForm.makale_link || ""} onChange={e => setAdminForm({...adminForm, makale_link: e.target.value})} placeholder="https://..." />
                    {(adminForm.makale_dosya_turu || "link") !== "link" && <p className="text-xs text-gray-500 mt-1">Dosyayı Google Drive'a yükleyip "Herkesle paylaş" linkini yapıştırın.</p>}
                  </div>
                </div>
              )}

              {/* Kitap alanları */}
              {adminForm.tur === "kitap" && (
                <div className="p-4 bg-green-50 border border-green-200 rounded-xl space-y-4">
                  <div className="font-semibold text-sm text-green-800">📚 Kitap Bilgileri</div>

                  {/* Hızlı ekleme: ISBN veya Link */}
                  <div className="bg-white rounded-lg p-3 border border-green-100 space-y-3">
                    <p className="text-xs text-gray-500 font-medium">🔍 ISBN, barkod veya kitap sitesi linki ile otomatik bilgi çekin:</p>
                    <div className="flex gap-2">
                      <Input placeholder="ISBN veya Barkod (978...)" value={adminForm.kitap_isbn} onChange={e => setAdminForm({...adminForm, kitap_isbn: e.target.value})} className="flex-1" />
                      <Button type="button" size="sm" className="bg-green-600 text-white whitespace-nowrap" disabled={kitapYukleniyor || !adminForm.kitap_isbn.trim()} onClick={() => kitapBilgiCek(adminForm.kitap_isbn, 'isbn')}>
                        {kitapYukleniyor ? '⏳' : '🔍'} Ara
                      </Button>
                    </div>
                    <div className="flex gap-2">
                      <Input placeholder="Kitapyurdu, Amazon, D&R linki yapıştırın..." value={adminForm.kitap_link} onChange={e => setAdminForm({...adminForm, kitap_link: e.target.value})} className="flex-1" />
                      <Button type="button" size="sm" className="bg-blue-600 text-white whitespace-nowrap" disabled={kitapYukleniyor || !adminForm.kitap_link.trim()} onClick={() => kitapBilgiCek(adminForm.kitap_link, 'link')}>
                        {kitapYukleniyor ? '⏳' : '🔗'} Çek
                      </Button>
                    </div>
                  </div>

                  {/* Kapak önizleme + manuel alanlar */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {adminForm.kitap_kapak && (
                      <div className="flex justify-center">
                        <img src={adminForm.kitap_kapak} alt="Kapak" className="h-40 rounded-lg shadow-md object-cover" onError={e => { e.target.style.display = 'none'; }} />
                      </div>
                    )}
                    <div className={`space-y-3 ${adminForm.kitap_kapak ? 'md:col-span-2' : 'md:col-span-3'}`}>
                      <div><Label>Yazar</Label><Input value={adminForm.kitap_yazar} onChange={e => setAdminForm({...adminForm, kitap_yazar: e.target.value})} placeholder="Yazar adı" /></div>
                      <div className="grid grid-cols-2 gap-3">
                        <div><Label>Yayınevi</Label><Input value={adminForm.kitap_yayinevi} onChange={e => setAdminForm({...adminForm, kitap_yayinevi: e.target.value})} placeholder="Yayınevi" /></div>
                        <div><Label>Sayfa Sayısı</Label><Input value={adminForm.kitap_sayfa} onChange={e => setAdminForm({...adminForm, kitap_sayfa: e.target.value})} placeholder="Sayfa" /></div>
                      </div>
                      <div><Label>Yaş Grubu / Sınıf</Label><Input value={adminForm.kitap_yas_grubu} onChange={e => setAdminForm({...adminForm, kitap_yas_grubu: e.target.value})} placeholder="Örn: 8-10 yaş, 3. sınıf" /></div>
                    </div>
                  </div>
                </div>
              )}

              {/* Soru Ekleme */}
              <div className="border-2 border-dashed border-gray-200 rounded-xl p-4 space-y-4">
                <h4 className="font-semibold text-gray-700">Test Soruları ({adminForm.sorular.length} soru eklendi)</h4>
                {adminForm.sorular.map((s, i) => {
                  const taksLabel = {"bilgi":"1️⃣ Bilgi","kavrama":"2️⃣ Kavrama","uygulama":"3️⃣ Uygulama","analiz":"4️⃣ Analiz","sentez":"5️⃣ Sentez","degerlendirme":"6️⃣ Yaratma"};
                  const taksRenk = {"bilgi":"bg-blue-100 text-blue-700","kavrama":"bg-green-100 text-green-700","uygulama":"bg-yellow-100 text-yellow-700","analiz":"bg-orange-100 text-orange-700","sentez":"bg-red-100 text-red-700","degerlendirme":"bg-purple-100 text-purple-700"};
                  return (
                    <div key={i} className="bg-green-50 p-3 rounded-lg text-sm flex items-start justify-between">
                      <div><strong>{i+1}.</strong> {s.soru} {s.taksonomi && <span className={`text-[10px] ml-1 px-1.5 py-0.5 rounded-full ${taksRenk[s.taksonomi] || "bg-gray-100"}`}>{taksLabel[s.taksonomi] || ""}</span>}</div>
                      <button type="button" onClick={() => setAdminForm({...adminForm, sorular: adminForm.sorular.filter((_,idx)=>idx!==i)})}
                        className="text-red-500 ml-2 text-xs">✕</button>
                    </div>
                  );
                })}
                <div className="space-y-3 border-t pt-4">
                  {/* Bloom Taksonomisi Seçici */}
                  <div>
                    <Label className="text-xs font-medium text-gray-600">Bloom Taksonomisi Basamağı</Label>
                    <div className="grid grid-cols-3 gap-1.5 mt-1">
                      {[
                        {k:"bilgi", l:"1️⃣ Bilgi", r:"bg-blue-500"},
                        {k:"kavrama", l:"2️⃣ Kavrama", r:"bg-green-500"},
                        {k:"uygulama", l:"3️⃣ Uygulama", r:"bg-yellow-500"},
                        {k:"analiz", l:"4️⃣ Analiz", r:"bg-orange-500"},
                        {k:"sentez", l:"5️⃣ Sentez", r:"bg-red-500"},
                        {k:"degerlendirme", l:"6️⃣ Yaratma", r:"bg-purple-500"},
                      ].map(t => (
                        <button key={t.k} type="button" onClick={() => setYeniSoru({...yeniSoru, taksonomi: t.k})}
                          className={`px-2 py-1.5 rounded-lg text-xs font-medium border transition-all ${yeniSoru.taksonomi === t.k ? `${t.r} text-white border-transparent shadow` : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'}`}>{t.l}</button>
                      ))}
                    </div>
                  </div>
                  {/* Bloom ipucu */}
                  <div className={`rounded-lg p-2.5 text-xs border ${
                    yeniSoru.taksonomi === "bilgi" ? "bg-blue-50 border-blue-200" :
                    yeniSoru.taksonomi === "kavrama" ? "bg-green-50 border-green-200" :
                    yeniSoru.taksonomi === "uygulama" ? "bg-yellow-50 border-yellow-200" :
                    yeniSoru.taksonomi === "analiz" ? "bg-orange-50 border-orange-200" :
                    yeniSoru.taksonomi === "sentez" ? "bg-red-50 border-red-200" :
                    "bg-purple-50 border-purple-200"
                  }`}>
                    {yeniSoru.taksonomi === "bilgi" && (<><strong className="text-blue-700">Hatırlama:</strong> Metinde doğrudan geçen bilgiyi sorun. <span className="italic text-gray-500">Kim? Ne zaman? Nerede? Hangisi metinde geçmiştir?</span></>)}
                    {yeniSoru.taksonomi === "kavrama" && (<><strong className="text-green-700">Anlama:</strong> Kendi cümleleriyle ifade etsin. <span className="italic text-gray-500">Ne anlatılmak istenmiştir? Ana fikir nedir? Özetleyiniz.</span></>)}
                    {yeniSoru.taksonomi === "uygulama" && (<><strong className="text-yellow-700">Uygulama:</strong> Farklı bir durumda kullanmasını isteyin. <span className="italic text-gray-500">Sen olsaydın? Bu bilgiyi nerede kullanabilirsin?</span></>)}
                    {yeniSoru.taksonomi === "analiz" && (<><strong className="text-orange-700">Analiz:</strong> Neden-sonuç, karşılaştırma sorun. <span className="italic text-gray-500">Neden böyle davrandı? Aradaki fark nedir? Sebebi ne?</span></>)}
                    {yeniSoru.taksonomi === "sentez" && (<><strong className="text-red-700">Değerlendirme:</strong> Yargılama ve görüş bildirme. <span className="italic text-gray-500">Katılıyor musun? Doğru mu yanlış mı? En önemli mesaj ne?</span></>)}
                    {yeniSoru.taksonomi === "degerlendirme" && (<><strong className="text-purple-700">Yaratma:</strong> Yeni bir şey üretme, tasarlama. <span className="italic text-gray-500">Farklı bir son yaz. Başlık öner. Devamını tahmin et.</span></>)}
                  </div>
                  <Input placeholder={
                    yeniSoru.taksonomi === "bilgi" ? "Metinde ... kim / ne zaman / nerede?" :
                    yeniSoru.taksonomi === "kavrama" ? "Bu bölümde anlatılmak istenen nedir?" :
                    yeniSoru.taksonomi === "uygulama" ? "Sen olsaydın bu durumda ne yapardın?" :
                    yeniSoru.taksonomi === "analiz" ? "Karakterin böyle davranmasının sebebi nedir?" :
                    yeniSoru.taksonomi === "sentez" ? "Bu karara katılıyor musun? Neden?" :
                    "Hikayeye farklı bir son yaz"
                  } value={yeniSoru.soru} onChange={e => setYeniSoru({...yeniSoru, soru: e.target.value})} />
                  {yeniSoru.secenekler.map((s, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <span className="text-sm font-bold w-5">{['A','B','C','D'][i]}</span>
                      <Input placeholder={`${['A','B','C','D'][i]} seçeneği`} value={s} onChange={e => { const sec=[...yeniSoru.secenekler]; sec[i]=e.target.value; setYeniSoru({...yeniSoru, secenekler:sec}); }} />
                      <input type="radio" name="dogru" checked={yeniSoru.dogru_cevap===i} onChange={() => setYeniSoru({...yeniSoru, dogru_cevap:i})} className="w-4 h-4 accent-orange-500" title="Doğru cevap" />
                    </div>
                  ))}
                  <p className="text-xs text-gray-500">● Doğru cevabı radyo butonuyla işaretleyin</p>
                  <Button type="button" variant="outline" size="sm" onClick={soruEkle} className="w-full">+ Soru Ekle</Button>
                </div>
              </div>

              <div className="flex gap-3">
                <Button type="submit" className="flex-1 bg-gradient-to-r from-orange-500 to-red-500 text-white">
                  {(user.role === "admin" || user.role === "coordinator") ? "Oylama Başlat" : "Yöneticiye Gönder"}
                </Button>
                <Button type="button" variant="outline" onClick={() => setGorunum("liste")} className="flex-1">İptal</Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ── ANA LİSTE GÖRÜNÜMÜ ──
  const bekleyenler = icerikler.filter(i => i.durum === "beklemede");
  const oylamadakiler = icerikler.filter(i => i.durum === "oylama");
  const yayindakiler = icerikler.filter(i => i.durum === "yayinda");
  const reddedilenler = icerikler.filter(i => i.durum === "reddedildi");

  return (
    <div className="space-y-6">
      {/* Alt sekme: İçerikler / Egzersizler */}
      <div className="flex gap-2 mb-2">
        <button className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${gelisimSekme === 'icerikler' ? 'bg-orange-500 text-white shadow' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`} onClick={() => setGelisimSekme('icerikler')}>📚 İçerikler</button>
        <button className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${gelisimSekme === 'egzersizler' ? 'bg-blue-500 text-white shadow' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`} onClick={() => setGelisimSekme('egzersizler')}>👁️ Egzersizler</button>
        <button className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${gelisimSekme === 'gorevler' ? 'bg-green-500 text-white shadow' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`} onClick={() => setGelisimSekme('gorevler')}>📌 Görevler</button>
        <button className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${gelisimSekme === 'kurslar' ? 'bg-indigo-500 text-white shadow' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`} onClick={() => { if (onTabChange) onTabChange('courses'); }}>📖 Kurslar</button>
        <button className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${gelisimSekme === 'ai-bilgi' ? 'bg-cyan-500 text-white shadow' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`} onClick={() => setGelisimSekme('ai-bilgi')}>🧠 AI Eğit</button>
        {user.role === 'admin' && (
          <button className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${gelisimSekme === 'puan-ayar' ? 'bg-purple-500 text-white shadow' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'}`} onClick={() => setGelisimSekme('puan-ayar')}>⚙️ Egzersiz Puanları</button>
        )}
      </div>

      {/* Görevler alt sekmesi */}
      {/* AI Bilgi Tabanı — PDF/Word yükleme */}
      {gelisimSekme === 'ai-bilgi' && (() => {

        const dosyaYukle = async () => {
          const urlMod = yukleForm._mod === "url";

          if (urlMod) {
            // ── URL MODU ──
            const url = (yukleForm._url || "").trim();
            if (!url) { toast({ title: "Link yapıştırın", variant: "destructive" }); return; }
            if (!url.startsWith("http")) { toast({ title: "Geçerli bir link girin (http:// veya https://)", variant: "destructive" }); return; }
            setAiBilgiYukleniyor(true); setAiIlerleme(5); setAiIslemDurum("🔗 Dosya linkten indiriliyor..."); setAiSonuc(null);
            try {
              const r = await axios.post(`${API}/ai/bilgi-tabani/yukle-url`, { url, sinif: parseInt(yukleForm.sinif), tur: yukleForm.tur, kitap_adi: yukleForm.kitap_adi, yazar: yukleForm.yazar });
              toast({ title: `🧠 ${r.data.mesaj}` });
              setAiIlerleme(25); setAiIslemDurum("📖 Metin çıkarılıyor...");
              const yukId = r.data.yukleme?.id;
              if (yukId) {
                const ilerlemeTakip = setInterval(async () => {
                  try {
                    const ir = await axios.get(`${API}/ai/bilgi-tabani/ilerleme/${yukId}`);
                    setAiIlerleme(ir.data.ilerleme || 25);
                    const d = ir.data.durum;
                    setAiIslemDurum(d === "metin_cikariliyor" ? "📖 Metin çıkarılıyor..." : d === "ai_analiz" ? "🧠 AI analiz ediyor..." : d === "tamamlandi" ? "✅ Tamamlandı!" : d === "hata" ? "❌ Hata" : "⏳ İşleniyor...");
                    if (d === "tamamlandi" || d === "hata") clearInterval(ilerlemeTakip);
                  } catch(e) {}
                }, 2000);
                const isleR = await axios.post(`${API}/ai/bilgi-tabani/isle/${yukId}`, {}, { timeout: 300000 });
              try { const r2 = await axios.get(`${API}/ai/bilgi-tabani/gecmis`); setAiYuklemeler(Array.isArray(r2.data) ? r2.data : []); } catch(e) {}
              try { const r3 = await axios.get(`${API}/ai/bilgi-tabani/puanlarim`); setAiPuanlar(r3.data); } catch(e) {}
              try { const r4 = await axios.get(`${API}/ai/bilgi-tabani/istatistik`); setAiStat(r4.data); } catch(e) {}
            } catch(e) { toast({ title: e.response?.data?.detail || "Link yükleme hatası", variant: "destructive" }); setAiIslemDurum(""); }
            setAiBilgiYukleniyor(false);
            return;
          }

          // ── DOSYA MODU ──
          const file = dosyaRef.current?.files?.[0];
          if (!file) { toast({ title: "Dosya seçin", variant: "destructive" }); return; }
          const ext = file.name.split('.').pop().toLowerCase();
          if (!['pdf', 'docx', 'doc'].includes(ext)) { toast({ title: "Sadece PDF, DOCX veya DOC yüklenebilir", variant: "destructive" }); return; }
          setAiBilgiYukleniyor(true); setAiIlerleme(5); setAiIslemDurum("📤 Dosya yükleniyor..."); setAiSonuc(null);
          try {
            const fd = new FormData();
            fd.append("dosya", file);
            fd.append("sinif", yukleForm.sinif);
            fd.append("tur", yukleForm.tur);
            fd.append("kitap_adi", yukleForm.kitap_adi || file.name);
            fd.append("yazar", yukleForm.yazar);
            fd.append("temalar", yukleForm.temalar || "");
            const r = await axios.post(`${API}/ai/bilgi-tabani/yukle`, fd, {
              headers: { "Content-Type": "multipart/form-data" },
              onUploadProgress: (p) => { if (p.total) setAiIlerleme(Math.round(p.loaded / p.total * 20)); }
            });
            toast({ title: `🧠 ${r.data.mesaj}` });
            const yukId = r.data.yukleme?.id;
            if (yukId) {
              setAiIlerleme(25); setAiIslemDurum("📖 Metin çıkarılıyor...");
              const ilerlemeTakip = setInterval(async () => {
                try {
                  const ir = await axios.get(`${API}/ai/bilgi-tabani/ilerleme/${yukId}`);
                  setAiIlerleme(ir.data.ilerleme || 25);
                  const d = ir.data.durum;
                  setAiIslemDurum(d === "metin_cikariliyor" ? "📖 Metin çıkarılıyor..." : d === "ai_analiz" ? "🧠 AI analiz ediyor..." : d === "tamamlandi" ? "✅ Tamamlandı!" : d === "hata" ? "❌ Hata" : "⏳ İşleniyor...");
                  if (d === "tamamlandi" || d === "hata") clearInterval(ilerlemeTakip);
                } catch(e) {}
              }, 2000);
              const isleR = await axios.post(`${API}/ai/bilgi-tabani/isle/${yukId}`, {}, { timeout: 300000 });
              clearInterval(ilerlemeTakip);
              setAiIlerleme(100); setAiIslemDurum("✅ Tamamlandı!");
              setAiSonuc(isleR.data);
              const mockUyari = isleR.data.mock ? " (Demo mod — API key olmadan)" : "";
              toast({ title: `🎉 AI öğrendi!${mockUyari} ${isleR.data.cikarilan_kelime || 0} kelime, ${isleR.data.okuma_parcasi || 0} parça, ${isleR.data.uretilen_soru || 0} soru` });
            }
            dosyaRef.current.value = "";
            setYukleForm({ sinif: "3", tur: "ders_kitabi", kitap_adi: "", yazar: "", temalar: "", _mod: "dosya" });
            try { const r2 = await axios.get(`${API}/ai/bilgi-tabani/gecmis`); setAiYuklemeler(Array.isArray(r2.data) ? r2.data : []); } catch(e) {}
            try { const r3 = await axios.get(`${API}/ai/bilgi-tabani/puanlarim`); setAiPuanlar(r3.data); } catch(e) {}
            try { const r4 = await axios.get(`${API}/ai/bilgi-tabani/istatistik`); setAiStat(r4.data); } catch(e) {}
          } catch(e) { toast({ title: e.response?.data?.detail || "Yükleme hatası", variant: "destructive" }); setAiIslemDurum(""); }
          setAiBilgiYukleniyor(false);
        };

        // Geçmiş yüklemenin sonuçlarını görüntüle
        const sonucGoruntule = async (yukId) => {
          try {
            const r = await axios.get(`${API}/ai/bilgi-tabani/sonuc/${yukId}`);
            setAiSonuc({ kelimeler: r.data.kelimeler, parcalar: r.data.parcalar, sorular: r.data.sorular, ...r.data.yukleme?.sonuc });
            setAiSonucSekme("kelimeler");
          } catch(e) { toast({ title: "Sonuç yüklenemedi", variant: "destructive" }); }
        };

        return (<div className="space-y-4">
          {/* Puan özeti */}
          <div className="bg-gradient-to-r from-cyan-500 to-blue-600 rounded-2xl p-4 text-white">
            <div className="flex items-center justify-between">
              <div><div className="text-sm opacity-80">🧠 AI Eğitim Puanım</div><div className="text-3xl font-bold">{aiPuanlar.toplam}</div></div>
              <div className="text-right"><div className="text-sm opacity-80">Yüklemelerim</div><div className="text-2xl font-bold">{aiYuklemeler.length}</div></div>
            </div>
          </div>

          {/* İstatistikler */}
          {aiStat && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div className="bg-white rounded-xl p-3 border text-center"><div className="text-xl font-bold text-cyan-600">{aiStat.toplam_yukleme}</div><div className="text-[10px] text-gray-500">Toplam Yükleme</div></div>
              <div className="bg-white rounded-xl p-3 border text-center"><div className="text-xl font-bold text-green-600">{aiStat.toplam_kelime}</div><div className="text-[10px] text-gray-500">Toplam Kelime</div></div>
              <div className="bg-white rounded-xl p-3 border text-center"><div className="text-xl font-bold text-purple-600">{aiStat.toplam_ai_soru}</div><div className="text-[10px] text-gray-500">AI Sorusu</div></div>
              <div className="bg-white rounded-xl p-3 border text-center"><div className={`text-xl font-bold ${(aiStat.guven_skoru?.ortalama || 0) >= 70 ? 'text-green-600' : (aiStat.guven_skoru?.ortalama || 0) >= 40 ? 'text-yellow-600' : 'text-red-500'}`}>{aiStat.guven_skoru?.ortalama || "—"}</div><div className="text-[10px] text-gray-500">Ort. Güven Skoru</div></div>
            </div>
          )}

          {/* Top katkıcılar */}
          {aiStat?.top_contributors?.length > 0 && (
            <div className="bg-white rounded-xl p-3 border"><div className="text-xs font-bold text-gray-700 mb-2">🏆 En Çok Katkı Yapanlar</div>
              <div className="space-y-1">{aiStat.top_contributors.slice(0, 5).map((c, i) => (
                <div key={i} className="flex items-center justify-between text-xs"><span className="text-gray-600">{["🥇","🥈","🥉","4.","5."][i]} {c.ad}</span><span className="font-bold text-cyan-600">{c.puan} puan ({c.yukleme} dosya)</span></div>
              ))}</div>
            </div>
          )}

          {/* Yükleme formu */}
          <Card className="border-0 shadow-sm border-l-4 border-l-cyan-500">
            <CardHeader className="pb-2"><CardTitle className="text-sm">📤 AI'a Kitap / Doküman Öğret</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="bg-cyan-50 rounded-lg p-3 border border-cyan-100">
                <p className="text-xs text-cyan-700">📚 PDF veya Word dosyası yükleyin ya da direkt link yapıştırın. AI içeriği analiz ederek kelime haritası, okuma parçaları ve Bloom taksonomili sorular üretecek.</p>
                <p className="text-xs text-cyan-600 mt-1 font-medium">Her yükleme = +20 puan | Onay bonusu = +10 puan | Zengin içerik bonusu = +5 puan</p>
              </div>

              {/* Dosya / URL seçimi */}
              <div className="flex gap-1 bg-gray-100 rounded-lg p-0.5">
                <button onClick={() => setYukleForm({...yukleForm, _mod: "dosya"})} className={`flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${(!yukleForm._mod || yukleForm._mod === "dosya") ? 'bg-white shadow text-cyan-700' : 'text-gray-500'}`}>📁 Dosya Yükle</button>
                <button onClick={() => setYukleForm({...yukleForm, _mod: "url"})} className={`flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-all ${yukleForm._mod === "url" ? 'bg-white shadow text-cyan-700' : 'text-gray-500'}`}>🔗 Link Yapıştır</button>
              </div>

              {(!yukleForm._mod || yukleForm._mod === "dosya") && (
                <input ref={dosyaRef} type="file" accept=".pdf,.docx,.doc" className="block w-full text-sm text-gray-500 file:mr-2 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-cyan-100 file:text-cyan-700 hover:file:bg-cyan-200" />
              )}

              {yukleForm._mod === "url" && (
                <div className="space-y-2">
                  <Input value={yukleForm._url || ""} onChange={e => setYukleForm({...yukleForm, _url: e.target.value})} placeholder="https://tymm.meb.gov.tr/upload/kitap/turkce_1_1.pdf" className="text-xs" />
                  <p className="text-[10px] text-gray-400">PDF veya Word dosyasının direkt linkini yapıştırın. MEB, EBA veya herhangi bir kaynaktan olabilir.</p>
                </div>
              )}

              <div className="grid grid-cols-2 gap-2">
                <div><Label className="text-xs">Sınıf Seviyesi *</Label>
                  <Select value={yukleForm.sinif} onValueChange={v => setYukleForm({...yukleForm, sinif: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>{[1,2,3,4,5,6,7,8].map(s => <SelectItem key={s} value={String(s)}>{s}. Sınıf</SelectItem>)}</SelectContent>
                  </Select></div>
                <div><Label className="text-xs">Kitap Türü *</Label>
                  <Select value={yukleForm.tur} onValueChange={v => setYukleForm({...yukleForm, tur: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ders_kitabi">📘 MEB Ders Kitabı</SelectItem>
                      <SelectItem value="oyku">📖 Öykü Kitabı</SelectItem>
                      <SelectItem value="masal">🧚 Masal Kitabı</SelectItem>
                      <SelectItem value="roman">📕 Roman</SelectItem>
                      <SelectItem value="ansiklopedi">📚 Ansiklopedi</SelectItem>
                      <SelectItem value="diger">📄 Diğer</SelectItem>
                    </SelectContent></Select></div>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div><Label className="text-xs">Kitap Adı</Label><Input value={yukleForm.kitap_adi} onChange={e => setYukleForm({...yukleForm, kitap_adi: e.target.value})} placeholder="Otomatik alınır" /></div>
                <div><Label className="text-xs">Yazar</Label><Input value={yukleForm.yazar} onChange={e => setYukleForm({...yukleForm, yazar: e.target.value})} placeholder="Yazar adı" /></div>
              </div>
              <Button onClick={dosyaYukle} disabled={aiBilgiYukleniyor} className="w-full bg-cyan-600 text-white">{aiBilgiYukleniyor ? "⏳ Yükleniyor..." : "🧠 Yükle ve AI'a Öğret (+20 puan)"}</Button>

              {/* İlerleme Çubuğu */}
              {aiBilgiYukleniyor && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-xs"><span className="text-cyan-700 font-medium">{aiIslemDurum}</span><span className="text-gray-500">{aiIlerleme}%</span></div>
                  <div className="bg-gray-200 rounded-full h-3 overflow-hidden"><div className="h-3 bg-gradient-to-r from-cyan-500 to-blue-600 rounded-full transition-all duration-500" style={{width:`${aiIlerleme}%`}} /></div>
                  <div className="flex justify-between text-[9px] text-gray-400"><span>📤 Yükleme</span><span>📖 Parse</span><span>🧠 AI Analiz</span><span>💾 Kayıt</span><span>✅</span></div>
                </div>
              )}

              {/* AI Sonuç Ekranı */}
              {aiSonuc && (aiSonuc.kelimeler?.length > 0 || aiSonuc.parcalar?.length > 0 || aiSonuc.sorular?.length > 0) && (
                <div className="border-t-2 border-cyan-200 pt-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-bold text-sm text-cyan-800">🎉 AI Öğrenme Sonuçları</h3>
                    <button onClick={() => setAiSonuc(null)} className="text-xs text-gray-400 hover:text-red-400">✕ Kapat</button>
                  </div>

                  {/* Özet kartları */}
                  <div className="grid grid-cols-3 gap-2">
                    <div className="bg-green-50 rounded-xl p-3 text-center border border-green-200"><div className="text-2xl font-bold text-green-600">{aiSonuc.kelimeler?.length || aiSonuc.cikarilan_kelime || 0}</div><div className="text-[9px] text-green-700">📚 Kelime Çıkarıldı</div></div>
                    <div className="bg-blue-50 rounded-xl p-3 text-center border border-blue-200"><div className="text-2xl font-bold text-blue-600">{aiSonuc.parcalar?.length || aiSonuc.okuma_parcasi || 0}</div><div className="text-[9px] text-blue-700">📖 Okuma Parçası</div></div>
                    <div className="bg-purple-50 rounded-xl p-3 text-center border border-purple-200"><div className="text-2xl font-bold text-purple-600">{aiSonuc.sorular?.length || aiSonuc.uretilen_soru || 0}</div><div className="text-[9px] text-purple-700">📝 Soru Üretildi</div></div>
                  </div>

                  {/* Sekme butonları */}
                  <div className="flex gap-1">
                    {[["kelimeler","📚 Kelimeler"],["parcalar","📖 Parçalar"],["sorular","📝 Sorular"]].map(([k,l]) => (
                      <button key={k} onClick={() => setAiSonucSekme(k)} className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${aiSonucSekme === k ? 'bg-cyan-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>{l}</button>
                    ))}
                  </div>

                  {/* Kelimeler listesi */}
                  {aiSonucSekme === "kelimeler" && aiSonuc.kelimeler?.length > 0 && (
                    <div className="space-y-1.5 max-h-80 overflow-y-auto">{aiSonuc.kelimeler.map((k, i) => (
                      <div key={i} className="bg-white rounded-lg p-2.5 border shadow-sm">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-bold text-cyan-700">{k.kelime}</span>
                            <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${k.zorluk <= 3 ? 'bg-green-100 text-green-700' : k.zorluk <= 6 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'}`}>zorluk: {k.zorluk}/10</span>
                          </div>
                          <span className="text-[9px] text-gray-400">Bölüm {k.bolum}</span>
                        </div>
                        <div className="text-xs text-gray-600 mt-1">{k.anlam}</div>
                        {k.ornek_cumle && <div className="text-[10px] text-gray-400 mt-0.5 italic">"{k.ornek_cumle}"</div>}
                      </div>
                    ))}</div>
                  )}

                  {/* Okuma parçaları */}
                  {aiSonucSekme === "parcalar" && aiSonuc.parcalar?.length > 0 && (
                    <div className="space-y-2 max-h-80 overflow-y-auto">{aiSonuc.parcalar.map((p, i) => (
                      <div key={i} className="bg-white rounded-lg p-3 border shadow-sm">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-bold text-blue-700">📖 {p.baslik || `Bölüm ${p.bolum}`}</span>
                          {p.tema && <span className="text-[9px] bg-blue-100 text-blue-600 px-1.5 py-0.5 rounded-full">{p.tema}</span>}
                        </div>
                        <p className="text-xs text-gray-600">{p.ozet}</p>
                        {p.metin_kesit && <details className="mt-1"><summary className="text-[10px] text-cyan-600 cursor-pointer">Metin kesiti göster</summary><p className="text-[10px] text-gray-400 mt-1 whitespace-pre-wrap bg-gray-50 p-2 rounded">{p.metin_kesit}</p></details>}
                      </div>
                    ))}</div>
                  )}

                  {/* Sorular */}
                  {aiSonucSekme === "sorular" && aiSonuc.sorular?.length > 0 && (
                    <div className="space-y-2 max-h-80 overflow-y-auto">{aiSonuc.sorular.map((s, i) => {
                      const taksRenk = {"bilgi":"bg-blue-100 text-blue-700","kavrama":"bg-green-100 text-green-700","uygulama":"bg-yellow-100 text-yellow-700","analiz":"bg-orange-100 text-orange-700","sentez":"bg-red-100 text-red-700","degerlendirme":"bg-purple-100 text-purple-700"};
                      return (
                        <div key={i} className="bg-white rounded-lg p-3 border shadow-sm">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-medium">{i+1}. {s.soru}</span>
                          </div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`text-[9px] px-1.5 py-0.5 rounded-full ${taksRenk[s.taksonomi] || 'bg-gray-100'}`}>{s.taksonomi}</span>
                            <span className="text-[9px] text-gray-400">Bölüm {s.bolum}</span>
                          </div>
                          <div className="grid grid-cols-2 gap-1">{(s.secenekler || []).map((sec, j) => (
                            <div key={j} className={`text-[10px] px-2 py-0.5 rounded ${j === s.dogru_cevap ? 'bg-green-100 text-green-700 font-bold' : 'text-gray-500'}`}>{["A","B","C","D"][j]}) {sec}</div>
                          ))}</div>
                        </div>
                      );
                    })}</div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Yükleme geçmişi */}
          {aiYuklemeler.length > 0 && (<div>
            <h3 className="font-medium text-sm text-gray-700 mb-2">📋 Yükleme Geçmişi</h3>
            <div className="space-y-2">{aiYuklemeler.map(y => {
              const gs = y.guven_skoru;
              const gsRenk = gs ? (gs.toplam >= 70 ? 'text-green-600 bg-green-50' : gs.toplam >= 40 ? 'text-yellow-600 bg-yellow-50' : 'text-red-600 bg-red-50') : '';
              return (
              <div key={y.id} className={`bg-white rounded-xl p-3 border shadow-sm ${!y.onayli ? 'border-l-4 border-l-yellow-400' : ''}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{y.dosya_format === '.pdf' ? '📕' : '📘'}</span>
                    <div><div className="text-sm font-medium">{y.kitap_adi}</div><div className="text-[10px] text-gray-500">{y.sinif}. Sınıf • {y.tur} • {y.dosya_format} • {(y.dosya_boyut / 1024 / 1024).toFixed(1)} MB</div></div>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* AI Güven Skoru */}
                    {gs && (<div className={`text-center px-2 py-1 rounded-lg ${gsRenk}`}>
                      <div className="text-sm font-bold">{gs.toplam}/100</div>
                      <div className="text-[8px]">Güven Skoru</div>
                    </div>)}
                    {/* Okuma Seviyesi */}
                    {y.okuma_seviyesi && (<div className="text-center px-2 py-1 rounded-lg bg-blue-50 text-blue-600">
                      <div className="text-sm font-bold">{y.okuma_seviyesi.grade_level}. sınıf</div>
                      <div className="text-[8px]">Seviye</div>
                    </div>)}
                    <div className="text-right">
                      <span className={`text-[10px] px-2 py-0.5 rounded-full ${y.durum === 'tamamlandi' ? 'bg-green-100 text-green-700' : y.durum === 'hata' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>{y.durum === 'tamamlandi' ? '✅ Tamamlandı' : y.durum === 'hata' ? '❌ Hata' : '⏳ Bekliyor'}</span>
                    {y.durum === 'tamamlandi' && <button onClick={() => sonucGoruntule(y.id)} className="text-[9px] text-cyan-600 hover:underline mt-0.5">Sonuçları Gör →</button>}
                    {y.durum === 'yuklendi' && <button onClick={async () => { try { toast({ title: "🧠 AI işleme başlatılıyor..." }); await axios.post(`${API}/ai/bilgi-tabani/isle/${y.id}`); toast({ title: "✅ İşleme tamamlandı!" }); const r2 = await axios.get(`${API}/ai/bilgi-tabani/gecmis`); setAiYuklemeler(Array.isArray(r2.data)?r2.data:[]); } catch(e) { toast({ title: "İşleme hatası", variant: "destructive" }); } }} className="text-[9px] text-orange-600 hover:underline mt-0.5">AI ile İşle →</button>}
                      {!y.onayli && <div className="text-[9px] text-yellow-600 mt-0.5">Onay bekliyor</div>}
                    </div>
                  </div>
                </div>
                {/* Güven Skoru detay (varsa) */}
                {gs && gs.detay && (
                  <div className="mt-2 pt-2 border-t border-gray-100 grid grid-cols-4 gap-1">
                    {Object.entries(gs.detay).map(([k, v]) => (
                      <div key={k} className="text-center">
                        <div className="bg-gray-100 rounded-full h-1 mb-0.5"><div className={`h-1 rounded-full ${v.skor >= v.max * 0.7 ? 'bg-green-500' : v.skor >= v.max * 0.4 ? 'bg-yellow-500' : 'bg-red-400'}`} style={{width: `${(v.skor / v.max) * 100}%`}} /></div>
                        <div className="text-[8px] text-gray-500">{({"kelime_cesitliligi":"Kelime","soru_kalitesi":"Soru","zorluk_uyumu":"Zorluk","icerik_zenginligi":"İçerik"})[k]} {v.skor}/{v.max}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>);
            })}</div>
          </div>)}
        </div>);
      })()}

      {gelisimSekme === 'gorevler' && (
        <GorevYonetimi user={user} students={students} teachers={teachers} />
      )}

      {gelisimSekme === 'egzersizler' && (
        <EgzersizlerModul user={user} egzersizPuanlari={egzersizPuanlari} onTamamla={async (egzersizId) => {
          try {
            const r = await axios.post(`${API}/egzersiz/tamamla`, { kullanici_id: user.id, egzersiz_id: egzersizId });
            toast({ title: `🎉 +${r.data.kazanilan_puan} puan kazandınız!` });
            fetchAll();
          } catch(e) {
            if (e.response?.status === 409) toast({ title: "Bu egzersizi bugün zaten yaptınız" });
            else toast({ title: "Hata", variant: "destructive" });
          }
        }} />
      )}

      {gelisimSekme === 'puan-ayar' && user.role === 'admin' && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-bold mb-4">⚙️ Egzersiz Puan Ayarları</h3>
          <p className="text-sm text-gray-500 mb-4">Her egzersiz tamamlandığında öğrencinin kazanacağı puanı belirleyin.</p>
          <div className="space-y-3">
            {[
              {id:'goz-takip', ad:'👁️ Göz Takip'},
              {id:'goz-sekiz', ad:'♾️ Sonsuzluk (∞)'},
              {id:'goz-zigzag', ad:'⚡ Zigzag Okuma'},
              {id:'goz-genisletme', ad:'🔭 Görüş Alanı Genişletme'},
              {id:'odaklanma', ad:'🎯 Odaklanma Noktası'},
              {id:'periferik', ad:'🌀 Periferik Görüş'},
              {id:'schulte', ad:'🔢 Schulte Tablosu'},
              {id:'goz-yoga', ad:'🧘 Göz Yoga'},
              {id:'renk-eslestir', ad:'🎨 Renk Eşleştirme'},
              {id:'hizli-kelime', ad:'📖 Hızlı Kelime Okuma'},
              {id:'kelime-avcisi', ad:'🔍 Kelime Avcısı'},
              {id:'ters-kelime', ad:'🔄 Ters Kelime Okuma'},
              {id:'eksik-harf', ad:'✏️ Eksik Harf Tamamlama'},
              {id:'karisik-cumle', ad:'🧩 Karışık Cümle Düzenleme'},
            ].map(eg => (
              <div key={eg.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <span className="text-sm font-medium">{eg.ad}</span>
                <div className="flex items-center gap-2">
                  <input type="number" min="0" max="100" className="w-20 border rounded-lg px-2 py-1 text-sm text-center"
                    value={egzersizPuanlari[eg.id] ?? 10}
                    onChange={e => setEgzersizPuanlari(prev => ({...prev, [eg.id]: parseInt(e.target.value) || 0}))} />
                  <span className="text-xs text-gray-500">puan</span>
                </div>
              </div>
            ))}
            <Button className="bg-purple-600 text-white mt-3" onClick={async () => {
              try {
                await axios.post(`${API}/egzersiz/puan-ayarla`, { puanlar: egzersizPuanlari });
                toast({ title: "Puanlar kaydedildi" });
              } catch { toast({ title: "Hata", variant: "destructive" }); }
            }}>💾 Kaydet</Button>
          </div>
        </div>
      )}

      {gelisimSekme === 'icerikler' && (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Başlık */}
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold">Gelişim Alanı</h2>
            {(user.role === "admin" || user.role === "teacher") && (
              <Button onClick={() => setGorunum("icerikEkle")} className="bg-gradient-to-r from-orange-500 to-red-500 text-white">
                <Plus className="h-4 w-4 mr-2"/>İçerik Ekle
              </Button>
            )}
          </div>

          {/* Yönetici onayı bekleyenler */}
          {(user.role === "admin" || user.role === "coordinator") && bekleyenler.length > 0 && (
            <div>
              <h3 className="font-semibold text-yellow-700 mb-3">⏳ Onay Bekleyenler ({bekleyenler.length})</h3>
              <div className="space-y-3">
                {bekleyenler.map(icerik => {
                  const isAcik = acikDetayId === "bek-" + icerik.id;
                  return (
                    <Card key={icerik.id} className="border-2 border-yellow-200 shadow-sm">
                      <CardContent className="p-0">
                        <div className="flex items-start justify-between p-5 cursor-pointer hover:bg-yellow-50/50 transition-colors" onClick={() => setAcikDetayId(isAcik ? null : "bek-" + icerik.id)}>
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${turColor(icerik.tur)}`}>{turIcon(icerik.tur)}</div>
                            <div><div className="font-semibold">{icerik.baslik}</div><div className="text-xs text-gray-500">{turLabel(icerik.tur)} • Ekleyen: {icerik.ekleyen_ad} • {icerik.sorular?.length || 0} soru</div></div>
                          </div>
                          <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${isAcik ? 'rotate-180' : ''}`} />
                        </div>
                        {isAcik && (
                          <div className="px-5 pb-3 space-y-3 border-t border-yellow-100 pt-3">
                            {icerik.aciklama && <div className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3 whitespace-pre-wrap">{icerik.aciklama}</div>}
                            {icerik.makale_link && <a href={icerik.makale_link} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline block">📎 {icerik.makale_link}</a>}
                            {icerik.kitap_yazar && <div className="text-sm text-gray-600">📚 Yazar: {icerik.kitap_yazar}</div>}
                            {icerik.kitap_kapak && <img src={icerik.kitap_kapak} alt="Kapak" className="h-28 rounded-lg shadow" onError={e => { e.target.style.display='none'; }} />}
                            {icerik.sorular?.length > 0 && (<div className="bg-blue-50 rounded-lg p-3"><div className="text-xs font-medium text-blue-700 mb-2">📝 {icerik.sorular.length} Test Sorusu</div>{icerik.sorular.map((s, i) => (<div key={i} className="text-sm text-gray-700 mb-3 pb-3 border-b border-blue-100 last:border-0"><div className="font-medium mb-1">{i+1}. {s.soru}</div><div className="grid grid-cols-2 gap-1 ml-4">{(s.secenekler || []).map((sec, j) => (<div key={j} className={`text-xs px-2 py-1 rounded ${j === s.dogru_cevap ? 'bg-green-100 text-green-700 font-bold' : 'bg-white text-gray-600'}`}>{['A','B','C','D'][j]}) {sec}</div>))}</div></div>))}</div>)}
                            <div className="text-xs text-gray-400">Hedef: {({"hepsi":"Herkes","ogretmen":"Öğretmenler","ogrenci":"Öğrenciler"})[icerik.hedef_kitle] || icerik.hedef_kitle}</div>
                          </div>
                        )}
                        <div className="px-5 pb-5 flex gap-2 flex-wrap">
                          <Button size="sm" onClick={() => adminKarar(icerik.id, true, false)} className="bg-blue-600 hover:bg-blue-700 text-white">🗳️ Oylama Başlat</Button>
                          <Button size="sm" onClick={() => adminKarar(icerik.id, true, true)} className="bg-green-600 hover:bg-green-700 text-white">✅ Direkt Yayına Al</Button>
                          <Button size="sm" variant="destructive" onClick={() => adminKarar(icerik.id, false)}>❌ Reddet</Button>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {/* Oylama bekleyenler */}
          {oylamadakiler.length > 0 && (user.role === "admin" || user.role === "teacher") && (
            <div>
              <h3 className="font-semibold text-blue-700 mb-3">🗳️ Oylaması Bekleyenler ({oylamadakiler.length})</h3>
              <div className="space-y-3">
                {oylamadakiler.map(icerik => {
                  const kullandi = oyKullandi(icerik);
                  const oran = onayOrani(icerik);
                  const oyCount = Object.keys(icerik.oylar || {}).length;
                  const isAcik = acikDetayId === icerik.id;
                  return (
                    <Card key={icerik.id} className="border-2 border-blue-200 shadow-sm">
                      <CardContent className="p-0">
                        {/* Başlık - tıklanabilir */}
                        <div className="flex items-start justify-between p-5 cursor-pointer hover:bg-blue-50/50 transition-colors" onClick={() => setAcikDetayId(isAcik ? null : icerik.id)}>
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${turColor(icerik.tur)}`}>{turIcon(icerik.tur)}</div>
                            <div>
                              <div className="font-semibold">{icerik.baslik}</div>
                              <div className="text-xs text-gray-500">{turLabel(icerik.tur)} • Ekleyen: {icerik.ekleyen_ad}</div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {oran !== null && (<div className="text-right"><div className="text-lg font-bold text-blue-600">%{oran}</div><div className="text-xs text-gray-500">{oyCount} oy</div></div>)}
                            <ChevronDown className={`h-4 w-4 text-gray-400 transition-transform ${isAcik ? 'rotate-180' : ''}`} />
                          </div>
                        </div>

                        {/* Detay - açılır */}
                        {isAcik && (
                          <div className="px-5 pb-5 space-y-3 border-t border-blue-100 pt-3">
                            {icerik.aciklama && <div className="text-sm text-gray-700 bg-gray-50 rounded-lg p-3 whitespace-pre-wrap">{icerik.aciklama}</div>}
                            {icerik.makale_link && <a href={icerik.makale_link} target="_blank" rel="noreferrer" className="text-sm text-blue-600 hover:underline block">📎 {icerik.makale_dosya_turu === "link" ? "Makale Linki" : "Dosya Linki"}: {icerik.makale_link}</a>}
                            {icerik.kitap_yazar && <div className="text-sm text-gray-600">📚 Yazar: {icerik.kitap_yazar}</div>}
                            {icerik.kitap_yayinevi && <div className="text-sm text-gray-600">🏢 Yayınevi: {icerik.kitap_yayinevi}</div>}
                            {icerik.kitap_kapak && <img src={icerik.kitap_kapak} alt="Kapak" className="h-28 rounded-lg shadow" onError={e => { e.target.style.display='none'; }} />}
                            {icerik.sorular?.length > 0 && (<div className="bg-blue-50 rounded-lg p-3"><div className="text-xs font-medium text-blue-700 mb-2">📝 {icerik.sorular.length} Test Sorusu</div>{icerik.sorular.map((s, i) => (<div key={i} className="text-sm text-gray-700 mb-3 pb-3 border-b border-blue-100 last:border-0"><div className="font-medium mb-1">{i+1}. {s.soru}</div><div className="grid grid-cols-2 gap-1 ml-4">{(s.secenekler || []).map((sec, j) => (<div key={j} className={`text-xs px-2 py-1 rounded ${j === s.dogru_cevap ? 'bg-green-100 text-green-700 font-bold' : 'bg-white text-gray-600'}`}>{['A','B','C','D'][j]}) {sec}</div>))}</div></div>))}</div>)}
                            <div className="text-xs text-gray-400">Hedef: {({"hepsi":"Herkes","ogretmen":"Öğretmenler","ogrenci":"Öğrenciler"})[icerik.hedef_kitle] || icerik.hedef_kitle} • Eklenme: {new Date(icerik.olusturma_tarihi).toLocaleDateString("tr-TR")}</div>
                          </div>
                        )}

                        {/* Oy bar + butonlar */}
                        <div className="px-5 pb-5">
                          {oran !== null && (<div className="mb-3"><div className="w-full bg-gray-200 rounded-full h-2"><div className={`h-2 rounded-full transition-all ${oran >= 60 ? 'bg-green-500' : 'bg-orange-500'}`} style={{width:`${oran}%`}}></div></div><p className="text-xs text-gray-500 mt-1">%60 onay gerekli • Şu an %{oran}</p></div>)}
                          {kullandi ? (<div className="text-sm text-gray-500 bg-gray-50 p-3 rounded-lg">✓ Oyunuzu kullandınız: <strong>{kullandi.onay ? "Onay ✅" : "Red ❌"}</strong>{!kullandi.onay && kullandi.sebep && <span className="text-gray-600"> — {kullandi.sebep}</span>}</div>
                          ) : (<div className="flex gap-2"><Button size="sm" onClick={() => oyVer(true, "", icerik)} className="bg-green-600 hover:bg-green-700 text-white flex-1">✅ Onayla (+2 puan)</Button><Button size="sm" variant="destructive" className="flex-1" onClick={() => { setRedDialogIcerik(icerik); }}>❌ Reddet</Button></div>)}
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {/* Yayındaki içerikler */}
          {yayindakiler.length > 0 && (
            <div>
              <h3 className="font-semibold text-green-700 mb-3">✅ Yayındaki İçerikler ({yayindakiler.length})</h3>
              <div className="space-y-3">
                {yayindakiler.map(icerik => {
                  const tamamlandi = isTamamlandi(icerik.id);
                  const puan = getPuan(icerik.id);
                  return (
                    <Card key={icerik.id} className={`border-0 shadow-sm ${tamamlandi ? 'opacity-75' : ''}`}>
                      <CardContent className="p-5">
                        <div className="flex items-start justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${turColor(icerik.tur)}`}>{turIcon(icerik.tur)}</div>
                            <div>
                              <div className="font-semibold">{icerik.baslik}</div>
                              <div className="text-xs text-gray-500">{turLabel(icerik.tur)} • {icerik.sorular?.length || 0} soru</div>
                              {icerik.aciklama && <div className="text-sm text-gray-600 mt-1">{icerik.aciklama}</div>}
                            </div>
                          </div>
                          <div className="flex flex-col items-end gap-2">
                            {tamamlandi && <span className="flex items-center gap-1 px-3 py-1 bg-green-100 text-green-700 rounded-full text-sm font-medium"><CheckCircle className="h-4 w-4"/>+{puan} puan</span>}
                            {(user.role === "admin" || user.role === "coordinator") && <Button variant="destructive" size="sm" onClick={async () => { try { await axios.delete(`${API}/gelisim/icerik/${icerik.id}`); fetchAll(); toast({title:"Silindi"}); } catch(e){} }}><Trash2 className="h-4 w-4"/></Button>}
                          </div>
                        </div>
                        {!tamamlandi && (
                          <div className="flex gap-2 mt-4 flex-wrap">
                            {icerik.sorular?.length > 0 && (
                              <Button size="sm" onClick={() => { setAktifIcerik(icerik); setGorunum("test"); setTestCevaplari([]); }}
                                className="bg-gradient-to-r from-orange-500 to-red-500 text-white">
                                📝 Testi Çöz (+10 puan)
                              </Button>
                            )}
                            <Button size="sm" variant="outline" onClick={() => handleTamamla(false, icerik)}>
                              ✓ Tamamlandı (+1 puan)
                            </Button>
                          </div>
                        )}
                        {/* Kitap türü ise bölüm bazlı soru yönetimi */}
                        {icerik.tur === "kitap" && (user.role === "admin" || user.role === "coordinator" || user.role === "teacher") && (
                          <Button size="sm" variant="outline" className="mt-2 text-teal-600 border-teal-300 hover:bg-teal-50" onClick={async () => {
                            setSoruYonetimiIcerik(icerik);
                            try { const r = await axios.get(`${API}/kitaplar/${icerik.id}/sorular`); setKitapSorulari(Array.isArray(r.data) ? r.data : []); } catch(e) { setKitapSorulari([]); }
                            setGorunum("soru-yonetimi");
                          }}>📝 Bölüm Soruları ({icerik._soru_sayisi || "Ekle"})</Button>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </div>
          )}

          {icerikler.length === 0 && (
            <div className="text-center py-16 text-gray-500">
              <Trophy className="h-16 w-16 mx-auto mb-4 text-gray-300"/>
              <p className="text-lg">Henüz içerik yok</p>
              <p className="text-sm">İlk içeriği eklemek için yukarıdaki butona tıklayın</p>
            </div>
          )}
        </div>

        {/* Puan Tablosu */}
        <div className="space-y-4">
          <Card className="border-0 shadow-sm">
            <CardHeader><CardTitle className="flex items-center gap-2"><Trophy className="h-5 w-5 text-yellow-500"/>Puan Tablosu</CardTitle></CardHeader>
            <CardContent>
              <div className="space-y-2">
                {puanTablosu.slice(0, 10).map((u, i) => (
                  <div key={i} className={`flex items-center justify-between p-3 rounded-xl ${u.ad === user.ad && u.soyad === user.soyad ? 'bg-orange-50 border border-orange-200' : 'bg-gray-50'}`}>
                    <div className="flex items-center gap-2">
                      <span className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold ${i===0?'bg-yellow-400 text-white':i===1?'bg-gray-300 text-gray-700':i===2?'bg-orange-300 text-white':'bg-gray-100 text-gray-600'}`}>{i+1}</span>
                      <div>
                        <div className="text-sm font-medium">{u.ad} {u.soyad}</div>
                        <div className="text-xs text-gray-400">{roleLabel(u.role)} {u.rozet_sayisi > 0 && `• 🏅${u.rozet_sayisi}`}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="font-bold text-orange-600">{u.toplam_puan} puan</span>
                      {u.rozet_puan > 0 && <div className="text-[10px] text-gray-400">🏅{u.rozet_puan} + ✍️{u.gelisim_puan}</div>}
                    </div>
                  </div>
                ))}
                {puanTablosu.length === 0 && <p className="text-sm text-gray-400 text-center py-4">Henüz puan yok</p>}
              </div>
            </CardContent>
          </Card>

          {/* Puan Rehberi */}
          <Card className="border-0 shadow-sm bg-gradient-to-br from-orange-50 to-yellow-50">
            <CardContent className="p-5">
              <h4 className="font-semibold text-gray-800 mb-3">🎯 Puan Rehberi</h4>
              <div className="space-y-2 text-sm text-gray-600">
                <div className="flex justify-between"><span>✅ İçerik tamamla</span><span className="font-bold text-orange-600">+1</span></div>
                <div className="flex justify-between"><span>📝 Test çöz (tam puan)</span><span className="font-bold text-orange-600">+10</span></div>
                <div className="flex justify-between"><span>🗳️ Oylama katıl</span><span className="font-bold text-orange-600">+2</span></div>
                <div className="flex justify-between"><span>🌟 İçeriğin yayına girdi</span><span className="font-bold text-orange-600">+5</span></div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
      )} {/* /gelisimSekme === icerikler */}

      {/* Red Sebebi Dialog */}
      <Dialog open={!!redDialogIcerik} onOpenChange={() => { setRedDialogIcerik(null); setRedSebep(""); }}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>❌ Reddetme Sebebi</DialogTitle>
            <DialogDescription>{redDialogIcerik?.baslik} içeriğini neden reddediyorsunuz?</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <textarea value={redSebep} onChange={e => setRedSebep(e.target.value)}
              placeholder="Lütfen reddetme sebebinizi açıklayın..." rows={4}
              className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500 resize-none" />
            <div className="flex gap-2">
              <Button variant="destructive" className="flex-1" disabled={!redSebep.trim()} onClick={() => oyVer(false, redSebep)}>Reddet</Button>
              <Button variant="outline" className="flex-1" onClick={() => { setRedDialogIcerik(null); setRedSebep(""); }}>İptal</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}


export default function App() {
  return <AppContent />;
}
