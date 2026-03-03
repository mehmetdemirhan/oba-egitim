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
import { Users, BookOpen, CreditCard, Plus, Edit2, Trash2, UserCheck, Calendar, ChevronDown, ChevronRight, Download, BarChart3, LogOut, Shield, Trophy, CheckCircle, BookMarked, Film, GraduationCap, Star, Stethoscope, Timer, FileText, Eye } from "lucide-react";
import { useToast } from "./hooks/use-toast";
import { Toaster } from "./components/ui/toaster";
import { ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Tooltip, XAxis, YAxis, CartesianGrid, AreaChart, Area } from 'recharts';
import * as XLSX from 'xlsx';
import { saveAs } from 'file-saver';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

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
  const [expandedDers, setExpandedDers] = useState(null);
  const [kursDersleri, setKursDersleri] = useState({});
  const [yeniDersForm, setYeniDersForm] = useState(null);
  const [yeniIcerikForm, setYeniIcerikForm] = useState(null);

  const availableCourses = ["Okuma Becerileri Temel", "Okuma Becerileri İleri", "Hızlı Okuma", "Anlama Becerileri", "Yazım Kuralları", "Dikkat Geliştirme", "Kelime Dağarcığı", "Metin Analizi"];
  const availableClasses = ["1","2","3","4","5","6","7","8","9"];

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${API}/dashboard`); setDashboardStats(r.data); } catch(e) {}
    try { if ((user?.role === 'admin' || user?.role === 'coordinator')) { const r = await axios.get(`${API}/dashboard/bekleyenler`); setBekleyenler(r.data); } } catch(e) { setBekleyenler({ metin_bekleyen:[], metin_oylama:[], gelisim_bekleyen:[], gelisim_oylama:[], toplam:0 }); }
    try { const r = await axios.get(`${API}/stats/weekly`); setWeeklyStats(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/stats/monthly`); setMonthlyStats(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/teachers`); setTeachers(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/students`); setStudents(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/courses`); setCourses(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/payments`); setPayments(r.data); } catch(e) {}
  }, []);

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
            <TabsTrigger value="courses" className={tabClass}><BookOpen className="h-4 w-4 mr-2" />Kurslar</TabsTrigger>
            {user.role !== "coordinator" && <TabsTrigger value="payments" className={tabClass}><CreditCard className="h-4 w-4 mr-2" />Muhasebe</TabsTrigger>}
            {user.role === "admin" && <TabsTrigger value="users" className={tabClass}><Shield className="h-4 w-4 mr-2" />Kullanıcılar</TabsTrigger>}
            <TabsTrigger value="gelisim" className={tabClass}><Trophy className="h-4 w-4 mr-2" />Gelişim</TabsTrigger>
            <TabsTrigger value="egzersizler" className={tabClass}><Eye className="h-4 w-4 mr-2" />Egzersizler</TabsTrigger>
            <TabsTrigger value="giris-analizi" className={tabClass}><Stethoscope className="h-4 w-4 mr-2" />Giriş Analizi</TabsTrigger>
          </TabsList>

          {/* Dashboard */}
          <TabsContent value="dashboard">
            {dashboardStats && (
              <div className="space-y-6">
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
                    <TableHeader><TableRow><TableHead>Ad Soyad</TableHead><TableHead>Sınıf</TableHead>{user.role !== "coordinator" && <TableHead>Veli</TableHead>}<TableHead>Öğretmen</TableHead>{user.role !== "coordinator" && <TableHead>Borç</TableHead>}<TableHead>İşlem</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {students.filter(s => showArchived.students || !s.arsivli).map(s => {
                        const t = teachers.find(t => t.id === s.ogretmen_id);
                        return (
                          <TableRow key={s.id} className={s.arsivli ? 'opacity-50 bg-gray-50' : ''}>
                            <TableCell className="font-medium">{s.ad} {s.soyad}</TableCell>
                            <TableCell>{s.sinif}</TableCell>
                            {user.role !== "coordinator" && <TableCell>{s.veli_ad} {s.veli_soyad}</TableCell>}
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
                                                {id:'renk-eslestirme', icon:'🎨', ad:'Şekil/Renk Eşleştirme', aciklama:'Hızlı eşleştirme'},
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

          {/* Egzersizler */}
          <TabsContent value="egzersizler">
            <EgzersizlerModul />
          </TabsContent>

          {/* Giris Analizi */}
          <TabsContent value="giris-analizi">
            <GirisAnaliziModul user={user} students={students} teachers={teachers} />
          </TabsContent>

          {/* Gelisim Alani */}
          <TabsContent value="gelisim">
            <GelisimAlani user={user} />
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
function BekleyenlerKarti({ bekleyenler, onRefresh, onTabChange }) {
  const { toast } = useToast();

  const adminKararMetin = async (id, onay, direkt = false) => {
    try {
      await axios.post(`${API}/diagnostic/texts/${id}/admin-karar`, { onay, direkt });
      toast({ title: direkt ? "✅ Direkt havuza alındı" : onay ? "🗳️ Oylama başlatıldı" : "❌ Reddedildi" });
      onRefresh();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const adminKararGelisim = async (id, onay, direkt = false) => {
    try {
      await axios.post(`${API}/gelisim/icerik/${id}/admin-karar`, { onay, direkt });
      toast({ title: direkt ? "✅ Direkt yayına alındı" : onay ? "🗳️ Oylama başlatıldı" : "❌ Reddedildi" });
      onRefresh();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const turLabel = { hikaye: "Hikaye", bilgilendirici: "Bilgilendirici", siir: "Şiir", hizmetici: "Hizmetiçi", film: "Film", kitap: "Kitap" };

  const satir = (item, tip) => {
    const isMetin = tip === "metin";
    const isBekleyen = (isMetin ? item.durum : item.durum) === "beklemede";
    return (
      <div key={item.id} className={`flex items-center justify-between p-3 rounded-xl border ${isBekleyen ? 'border-yellow-200 bg-yellow-50' : 'border-blue-100 bg-blue-50'}`}>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${isBekleyen ? 'bg-yellow-200 text-yellow-800' : 'bg-blue-200 text-blue-800'}`}>
              {isMetin ? "📄 Metin" : "📚 Gelişim"}
            </span>
            <span className={`text-xs px-2 py-0.5 rounded-full ${isBekleyen ? 'bg-yellow-100 text-yellow-700' : 'bg-blue-100 text-blue-700'}`}>
              {isBekleyen ? "⏳ Onay Bekliyor" : "🗳️ Oylamada"}
            </span>
          </div>
          <div className="font-semibold text-sm text-gray-800 mt-1 truncate">{item.baslik}</div>
          <div className="text-xs text-gray-500">
            {item.ekleyen_ad} •{" "}
            {isMetin ? `${item.sinif_seviyesi}. Sınıf • ${turLabel[item.tur] || item.tur}` : turLabel[item.tur] || item.tur}
            {" • "}{new Date(item.olusturma_tarihi).toLocaleDateString("tr-TR")}
          </div>
        </div>
        {isBekleyen && (
          <div className="flex gap-1 ml-3 shrink-0">
            <button onClick={() => isMetin ? adminKararMetin(item.id, true, true) : adminKararGelisim(item.id, true, true)}
              className="px-2 py-1 bg-green-600 hover:bg-green-700 text-white rounded-lg text-xs font-medium transition-colors">
              ✅ Direkt
            </button>
            <button onClick={() => isMetin ? adminKararMetin(item.id, true, false) : adminKararGelisim(item.id, true, false)}
              className="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-medium transition-colors">
              🗳️ Oylama
            </button>
            <button onClick={() => isMetin ? adminKararMetin(item.id, false) : adminKararGelisim(item.id, false)}
              className="px-2 py-1 bg-red-500 hover:bg-red-600 text-white rounded-lg text-xs font-medium transition-colors">
              ❌
            </button>
          </div>
        )}
        {!isBekleyen && (
          <div className="ml-3 text-xs text-blue-600 font-medium shrink-0">
            {Object.keys(item.oylar || {}).length} oy
          </div>
        )}
      </div>
    );
  };

  const tumListe = [
    ...bekleyenler.metin_bekleyen.map(i => ({ ...i, _tip: "metin" })),
    ...bekleyenler.gelisim_bekleyen.map(i => ({ ...i, _tip: "gelisim" })),
    ...bekleyenler.metin_oylama.map(i => ({ ...i, _tip: "metin" })),
    ...bekleyenler.gelisim_oylama.map(i => ({ ...i, _tip: "gelisim" })),
  ];

  return (
    <Card className="border-2 border-orange-200 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-orange-400 to-red-500 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-sm">{bekleyenler.toplam}</span>
            </div>
            <div>
              <div className="text-base font-bold">Onay Bekleyenler</div>
              <div className="text-xs text-gray-500 font-normal">
                {bekleyenler.metin_bekleyen.length + bekleyenler.gelisim_bekleyen.length} karar bekliyor •{" "}
                {bekleyenler.metin_oylama.length + bekleyenler.gelisim_oylama.length} oylamada
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => onTabChange("giris-analizi")}
              className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              📄 Metinler
            </button>
            <button onClick={() => onTabChange("gelisim")}
              className="text-xs px-3 py-1.5 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              📚 Gelişim
            </button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 max-h-80 overflow-y-auto">
        {tumListe.length === 0 && <p className="text-gray-400 text-sm text-center py-4">Bekleyen içerik yok</p>}
        {tumListe.map(item => satir(item, item._tip))}
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
      .then(r => setMetinler(r.data.filter(m => m.durum === "havuzda")))
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
function EgzersizlerModul() {
  const [aktifEgzersiz, setAktifEgzersiz] = useState(null);
  const [egzersizAyar, setEgzersizAyar] = useState({ hiz: 2, boyut: 40, sure: 30, kelimeHiz: 300 });
  const canvasRef = React.useRef(null);
  const animRef = React.useRef(null);
  const [calisiyorMu, setCalisiyorMu] = useState(false);
  const [kalanSure, setKalanSure] = useState(0);
  const [wpmKelimeler, setWpmKelimeler] = useState([]);
  const [wpmIndex, setWpmIndex] = useState(0);

  const egzersizler = [
    { id: 'goz-takip', baslik: 'Göz Takip Egzersizi', icon: '👁️', aciklama: 'Hareket eden topu gözlerinizle takip edin. Göz kaslarını güçlendirir.', renk: 'from-blue-500 to-cyan-500' },
    { id: 'goz-sekiz', baslik: 'Sonsuzluk (∞) Egzersizi', icon: '♾️', aciklama: 'Göz sonsuzluk şeklinde hareket eder. Odaklanma ve koordinasyonu geliştirir.', renk: 'from-purple-500 to-pink-500' },
    { id: 'goz-zigzag', baslik: 'Zigzag Okuma', icon: '⚡', aciklama: 'Göz zigzag şeklinde hareket eder. Satır takip hızını artırır.', renk: 'from-orange-500 to-red-500' },
    { id: 'goz-genisletme', baslik: 'Görüş Alanı Genişletme', icon: '🔭', aciklama: 'Merkeze odaklanırken çevresel görüşü genişletin.', renk: 'from-green-500 to-emerald-500' },
    { id: 'hizli-kelime', baslik: 'Hızlı Kelime Okuma (RSVP)', icon: '📖', aciklama: 'Kelimeler tek tek hızla gösterilir. Okuma hızını artırır.', renk: 'from-indigo-500 to-blue-500' },
    { id: 'odaklanma', baslik: 'Odaklanma Noktası', icon: '🎯', aciklama: 'Merkez noktaya odaklanın, çevredeki harfleri okumaya çalışın.', renk: 'from-teal-500 to-cyan-500' },
  ];

  const durdur = () => {
    setCalisiyorMu(false);
    if (animRef.current) { cancelAnimationFrame(animRef.current); animRef.current = null; }
  };

  const baslat = (id) => {
    setAktifEgzersiz(id);
    setCalisiyorMu(true);
    setKalanSure(egzersizAyar.sure);
  };

  // Geri sayım
  React.useEffect(() => {
    if (!calisiyorMu || kalanSure <= 0) { if (kalanSure <= 0 && calisiyorMu) durdur(); return; }
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
        // İç içe halkalar
        for (let r = 1; r <= 4; r++) {
          ctx.beginPath(); ctx.arc(W/2, H/2, r * 50, 0, Math.PI*2);
          ctx.strokeStyle = `rgba(99,102,241,${0.3 - r * 0.05})`; ctx.lineWidth = 1; ctx.stroke();
        }
        // Rastgele harfler
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
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {egzersizler.map(eg => (
              <div key={eg.id} className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden hover:shadow-md transition-shadow cursor-pointer" onClick={() => setAktifEgzersiz(eg.id)}>
                <div className={`bg-gradient-to-r ${eg.renk} p-6 text-center`}>
                  <span className="text-5xl">{eg.icon}</span>
                </div>
                <div className="p-4">
                  <h3 className="font-bold text-sm mb-1">{eg.baslik}</h3>
                  <p className="text-xs text-gray-500">{eg.aciklama}</p>
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
            </div>
          </div>
          {aktifEgzersiz === 'hizli-kelime' ? (
            <div className="bg-gray-900 rounded-2xl flex items-center justify-center" style={{height:'400px'}}>
              <div className="text-center">
                <div className="text-5xl font-bold text-white mb-4">{wpmKelimeler[wpmIndex] || ''}</div>
                <div className="text-gray-500 text-sm">{egzersizAyar.kelimeHiz} kelime/dakika • Kelime {wpmIndex + 1}/{wpmKelimeler.length}</div>
              </div>
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


function GelisimAlani({ user }) {
  const { toast } = useToast();
  const [icerikler, setIcerikler] = useState([]);
  const [tamamlananlar, setTamamlananlar] = useState([]);
  const [puanTablosu, setPuanTablosu] = useState([]);
  const [aktifIcerik, setAktifIcerik] = useState(null);
  const [gorunum, setGorunum] = useState("liste"); // liste, test, sonuc, icerikEkle
  const [testCevaplari, setTestCevaplari] = useState([]);
  const [sonuc, setSonuc] = useState(null);
  const [redSebep, setRedSebep] = useState("");
  const [redDialogIcerik, setRedDialogIcerik] = useState(null);
  const [adminForm, setAdminForm] = useState({ baslik: "", tur: "hizmetici", aciklama: "", hedef_kitle: "hepsi", sorular: [], makale_link: "", makale_dosya_turu: "link" });
  const [yeniSoru, setYeniSoru] = useState({ soru: "", secenekler: ["", "", "", ""], dogru_cevap: 0 });

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${API}/gelisim/icerik`); setIcerikler(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/gelisim/tamamlama/${user.id}`); setTamamlananlar(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/gelisim/puan-tablosu`); setPuanTablosu(r.data); } catch(e) {}
  }, [user.id]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

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

  const handleTamamla = async (testYapildi) => {
    try {
      const data = { icerik_id: aktifIcerik.id, kullanici_id: user.id };
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
    setYeniSoru({ soru: "", secenekler: ["", "", "", ""], dogru_cevap: 0 });
  };

  const icerikKaydet = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API}/gelisim/icerik`, adminForm);
      setAdminForm({ baslik: "", tur: "hizmetici", aciklama: "", hedef_kitle: "hepsi", sorular: [], makale_link: "", makale_dosya_turu: "link" });
      setGorunum("liste"); fetchAll();
      toast({ title: (user.role === "admin" || user.role === "coordinator") ? "İçerik oylama aşamasına alındı" : "İçerik yönetici onayına gönderildi" });
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  // ── TEST GÖRÜNÜMÜ ──
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
              <div className="grid grid-cols-2 gap-4">
                <div><Label>Tür</Label>
                  <Select value={adminForm.tur} onValueChange={v => setAdminForm({...adminForm, tur: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent position="popper" sideOffset={4} className="z-[200]">
                      <SelectItem value="hizmetici">🎓 Hizmetiçi Eğitim</SelectItem>
                      <SelectItem value="film">🎬 Film</SelectItem>
                      <SelectItem value="kitap">📚 Kitap</SelectItem>
                      <SelectItem value="makale">📄 Makale</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div><Label>Hedef Kitle</Label>
                  <Select value={adminForm.hedef_kitle} onValueChange={v => setAdminForm({...adminForm, hedef_kitle: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent position="popper" sideOffset={4} className="z-[200]">
                      <SelectItem value="hepsi">👥 Herkes</SelectItem>
                      <SelectItem value="ogretmen">👩‍🏫 Öğretmenler</SelectItem>
                      <SelectItem value="ogrenci">🎓 Öğrenciler</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div><Label>Açıklama</Label><Input value={adminForm.aciklama} onChange={e => setAdminForm({...adminForm, aciklama: e.target.value})} placeholder="Kısa açıklama..." /></div>

              {/* Makale alanları */}
              {adminForm.tur === "makale" && (
                <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl space-y-3">
                  <div className="font-semibold text-sm text-blue-800">📎 Makale Kaynağı</div>
                  <div><Label>Dosya Türü</Label>
                    <Select value={adminForm.makale_dosya_turu || "link"} onValueChange={v => setAdminForm({...adminForm, makale_dosya_turu: v})}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent position="popper" sideOffset={4} className="z-[200]">
                        <SelectItem value="link">🔗 Web Linki</SelectItem>
                        <SelectItem value="pdf">📕 PDF</SelectItem>
                        <SelectItem value="word">📘 Word</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>{(adminForm.makale_dosya_turu || "link") === "link" ? "URL" : "Paylaşım Linki (Drive/Dropbox)"}</Label>
                    <Input value={adminForm.makale_link || ""} onChange={e => setAdminForm({...adminForm, makale_link: e.target.value})} placeholder="https://..." />
                    {(adminForm.makale_dosya_turu || "link") !== "link" && <p className="text-xs text-gray-500 mt-1">Dosyayı Google Drive'a yükleyip "Herkesle paylaş" linkini yapıştırın.</p>}
                  </div>
                </div>
              )}

              {/* Soru Ekleme */}
              <div className="border-2 border-dashed border-gray-200 rounded-xl p-4 space-y-4">
                <h4 className="font-semibold text-gray-700">Test Soruları ({adminForm.sorular.length} soru eklendi)</h4>
                {adminForm.sorular.map((s, i) => (
                  <div key={i} className="bg-green-50 p-3 rounded-lg text-sm flex items-start justify-between">
                    <span><strong>{i+1}.</strong> {s.soru}</span>
                    <button type="button" onClick={() => setAdminForm({...adminForm, sorular: adminForm.sorular.filter((_,idx)=>idx!==i)})}
                      className="text-red-500 ml-2 text-xs">✕</button>
                  </div>
                ))}
                <div className="space-y-3 border-t pt-4">
                  <Input placeholder="Soru metni" value={yeniSoru.soru} onChange={e => setYeniSoru({...yeniSoru, soru: e.target.value})} />
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
                {bekleyenler.map(icerik => (
                  <Card key={icerik.id} className="border-2 border-yellow-200 shadow-sm">
                    <CardContent className="p-5">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-center gap-3">
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${turColor(icerik.tur)}`}>{turIcon(icerik.tur)}</div>
                          <div>
                            <div className="font-semibold">{icerik.baslik}</div>
                            <div className="text-xs text-gray-500">{turLabel(icerik.tur)} • Ekleyen: {icerik.ekleyen_ad} • {icerik.sorular?.length || 0} soru</div>
                          </div>
                        </div>
                      </div>
                      {icerik.aciklama && <p className="text-sm text-gray-600 mb-3">{icerik.aciklama}</p>}
                      <div className="flex gap-2 flex-wrap">
                        <Button size="sm" onClick={() => adminKarar(icerik.id, true, false)} className="bg-blue-600 hover:bg-blue-700 text-white">🗳️ Oylama Başlat</Button>
                        <Button size="sm" onClick={() => adminKarar(icerik.id, true, true)} className="bg-green-600 hover:bg-green-700 text-white">✅ Direkt Yayına Al</Button>
                        <Button size="sm" variant="destructive" onClick={() => adminKarar(icerik.id, false)}>❌ Reddet</Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
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
                  return (
                    <Card key={icerik.id} className="border-2 border-blue-200 shadow-sm">
                      <CardContent className="p-5">
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${turColor(icerik.tur)}`}>{turIcon(icerik.tur)}</div>
                            <div>
                              <div className="font-semibold">{icerik.baslik}</div>
                              <div className="text-xs text-gray-500">{turLabel(icerik.tur)} • Ekleyen: {icerik.ekleyen_ad}</div>
                            </div>
                          </div>
                          {oran !== null && (
                            <div className="text-right">
                              <div className="text-lg font-bold text-blue-600">%{oran}</div>
                              <div className="text-xs text-gray-500">{oyCount} oy</div>
                            </div>
                          )}
                        </div>
                        {icerik.aciklama && <p className="text-sm text-gray-600 mb-3">{icerik.aciklama}</p>}

                        {/* Oy bar */}
                        {oran !== null && (
                          <div className="mb-3">
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div className={`h-2 rounded-full transition-all ${oran >= 60 ? 'bg-green-500' : 'bg-orange-500'}`} style={{width:`${oran}%`}}></div>
                            </div>
                            <p className="text-xs text-gray-500 mt-1">%60 onay gerekli • Şu an %{oran}</p>
                          </div>
                        )}

                        {kullandi ? (
                          <div className="text-sm text-gray-500 bg-gray-50 p-3 rounded-lg">
                            ✓ Oyunuzu kullandınız: <strong>{kullandi.onay ? "Onay ✅" : "Red ❌"}</strong>
                            {!kullandi.onay && kullandi.sebep && <span className="text-gray-600"> — {kullandi.sebep}</span>}
                          </div>
                        ) : (
                          <div className="flex gap-2">
                            <Button size="sm" onClick={() => oyVer(true, "", icerik)} className="bg-green-600 hover:bg-green-700 text-white flex-1">✅ Onayla (+2 puan)</Button>
                            <Button size="sm" variant="destructive" className="flex-1" onClick={() => { setRedDialogIcerik(icerik); }}>❌ Reddet</Button>
                          </div>
                        )}
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
                          <div className="flex gap-2 mt-4">
                            {icerik.sorular?.length > 0 && (
                              <Button size="sm" onClick={() => { setAktifIcerik(icerik); setGorunum("test"); setTestCevaplari([]); }}
                                className="bg-gradient-to-r from-orange-500 to-red-500 text-white">
                                📝 Testi Çöz (+10 puan)
                              </Button>
                            )}
                            <Button size="sm" variant="outline" onClick={() => { setAktifIcerik(icerik); handleTamamla(false); }}>
                              ✓ Tamamlandı (+1 puan)
                            </Button>
                          </div>
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
                        <div className="text-xs text-gray-400">{roleLabel(u.role)}</div>
                      </div>
                    </div>
                    <span className="font-bold text-orange-600">{u.puan} puan</span>
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
