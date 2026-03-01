import React, { useState, useEffect, useCallback } from "react";
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
import { Users, BookOpen, CreditCard, Plus, Edit2, Trash2, UserCheck, Calendar, ChevronDown, ChevronRight, Download, BarChart3, LogOut, Shield, Trophy, CheckCircle, BookMarked, Film, GraduationCap, Star } from "lucide-react";
import { useToast } from "./hooks/use-toast";
import { Toaster } from "./components/ui/toaster";
import { ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell, Tooltip, XAxis, YAxis, CartesianGrid, AreaChart, Area } from 'recharts';
import * as XLSX from 'xlsx';
import { saveAs } from 'file-saver';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function roleLabel(role) {
  const labels = { admin: "Yönetici", teacher: "Öğretmen", student: "Öğrenci", parent: "Veli" };
  return labels[role] || role;
}

function UserManagement({ teachers }) {
  const { toast } = useToast();
  const [users, setUsers] = useState([]);
  const [form, setForm] = useState({ ad: "", soyad: "", email: "", password: "", role: "teacher", linked_id: "" });
  const [loading, setLoading] = useState(false);

  const fetchUsers = useCallback(async () => {
    try { const res = await axios.get(`${API}/auth/users`); setUsers(res.data); } catch (e) { console.error(e); }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const createUser = async (e) => {
    e.preventDefault(); setLoading(true);
    try {
      await axios.post(`${API}/auth/users`, form);
      setForm({ ad: "", soyad: "", email: "", password: "", role: "teacher", linked_id: "" });
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

  const roleBadgeColor = { admin: "bg-red-100 text-red-700", teacher: "bg-blue-100 text-blue-700", student: "bg-green-100 text-green-700", parent: "bg-purple-100 text-purple-700" };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <Card className="lg:col-span-1 border-0 shadow-sm">
        <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Kullanıcı</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={createUser} className="space-y-4">
            <div><Label>Ad</Label><Input value={form.ad} onChange={e => setForm({...form, ad: e.target.value})} required /></div>
            <div><Label>Soyad</Label><Input value={form.soyad} onChange={e => setForm({...form, soyad: e.target.value})} required /></div>
            <div><Label>E-posta</Label><Input type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} required /></div>
            <div><Label>Şifre</Label><Input type="password" value={form.password} onChange={e => setForm({...form, password: e.target.value})} required minLength={6} /></div>
            <div><Label>Rol</Label>
              <Select value={form.role} onValueChange={v => setForm({...form, role: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Yönetici</SelectItem>
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
            <TableHeader><TableRow><TableHead>Ad Soyad</TableHead><TableHead>E-posta</TableHead><TableHead>Rol</TableHead><TableHead>İşlem</TableHead></TableRow></TableHeader>
            <TableBody>
              {users.map(u => (
                <TableRow key={u.id}>
                  <TableCell>{u.ad} {u.soyad}</TableCell>
                  <TableCell>{u.email}</TableCell>
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
  const [weeklyStats, setWeeklyStats] = useState([]);
  const [monthlyStats, setMonthlyStats] = useState([]);
  const [teacherStudents, setTeacherStudents] = useState({});
  const [expandedTeachers, setExpandedTeachers] = useState(new Set());
  const [loadingAction, setLoadingAction] = useState(false);
  const [teacherForm, setTeacherForm] = useState({ ad: "", soyad: "", brans: "", telefon: "", seviye: "yeni", yapilmasi_gereken_odeme: 0 });
  const [studentForm, setStudentForm] = useState({ ad: "", soyad: "", sinif: "", veli_ad: "", veli_soyad: "", veli_telefon: "", aldigi_egitim: "", kur: "", yapilmasi_gereken_odeme: 0, ogretmene_yapilacak_odeme: 0, ogretmen_id: "" });
  const [courseForm, setCourseForm] = useState({ ad: "", fiyat: 0, sure: 0 });
  const [paymentForm, setPaymentForm] = useState({ tip: "ogrenci", kisi_id: "", miktar: 0, aciklama: "" });
  const [editingItem, setEditingItem] = useState(null);
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  const availableCourses = ["Okuma Becerileri Temel", "Okuma Becerileri İleri", "Hızlı Okuma", "Anlama Becerileri", "Yazım Kuralları", "Dikkat Geliştirme", "Kelime Dağarcığı", "Metin Analizi"];
  const availableClasses = ["1-A","1-B","1-C","2-A","2-B","2-C","3-A","3-B","3-C","4-A","4-B","4-C","5-A","5-B","5-C","6-A","6-B","6-C","7-A","7-B","7-C","8-A","8-B","8-C"];

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${API}/dashboard`); setDashboardStats(r.data); } catch(e) {}
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
  const fetchPayments = async () => { try { const r = await axios.get(`${API}/payments`); setPayments(r.data); } catch(e) {} };
  const fetchDashboard = async () => { try { const r = await axios.get(`${API}/dashboard`); setDashboardStats(r.data); } catch(e) {} };
  const fetchTeacherStudents = async (id) => { try { const r = await axios.get(`${API}/teachers/${id}/students`); setTeacherStudents(p => ({...p, [id]: r.data})); } catch(e) {} };

  const toggleTeacherExpansion = (id) => {
    const next = new Set(expandedTeachers);
    if (next.has(id)) { next.delete(id); } else { next.add(id); if (!teacherStudents[id]) fetchTeacherStudents(id); }
    setExpandedTeachers(next);
  };

  const formatCurrency = (v) => new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(v);
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
            <TabsTrigger value="payments" className={tabClass}><CreditCard className="h-4 w-4 mr-2" />Ödemeler</TabsTrigger>
            {user.role === "admin" && <TabsTrigger value="users" className={tabClass}><Shield className="h-4 w-4 mr-2" />Kullanıcılar</TabsTrigger>}
            <TabsTrigger value="gelisim" className={tabClass}><Trophy className="h-4 w-4 mr-2" />Gelişim</TabsTrigger>
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
                <CardHeader><CardTitle>Öğretmenler</CardTitle></CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {teachers.map(t => (
                      <div key={t.id} className="border border-gray-100 rounded-2xl overflow-hidden">
                        <div className="p-4 cursor-pointer hover:bg-gray-50 flex items-center justify-between" onClick={() => toggleTeacherExpansion(t.id)}>
                          <div className="flex items-center gap-4">
                            {expandedTeachers.has(t.id) ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                            <div><div className="font-medium">{t.ad} {t.soyad}</div><div className="text-sm text-gray-500">{t.brans} • {t.seviye}</div></div>
                          </div>
                          <div className="flex items-center gap-4">
                            <div className="text-center"><div className="text-sm font-medium">{t.ogrenci_sayisi}</div><div className="text-xs text-gray-500">Öğrenci</div></div>
                            <div className="flex gap-2">
                              <Button variant="outline" size="sm" onClick={e => { e.stopPropagation(); setEditingItem({type:'teacher',data:t}); setEditDialogOpen(true); }}><Edit2 className="h-4 w-4" /></Button>
                              <Button variant="destructive" size="sm" onClick={e => { e.stopPropagation(); deleteTeacher(t.id); }}><Trash2 className="h-4 w-4" /></Button>
                            </div>
                          </div>
                        </div>
                        {expandedTeachers.has(t.id) && (
                          <div className="border-t border-gray-100 bg-gray-50 p-4">
                            {teacherStudents[t.id] ? teacherStudents[t.id].map(s => (
                              <div key={s.id} className="bg-white p-3 rounded-xl border border-gray-100 mb-2">
                                <div className="font-medium text-sm">{s.ad} {s.soyad}</div>
                                <div className="text-xs text-gray-500">Kur: {s.kur} • Sınıf: {s.sinif}</div>
                              </div>
                            )) : <p className="text-sm text-gray-500">Yükleniyor...</p>}
                          </div>
                        )}
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
                <CardHeader><CardTitle>Öğrenciler</CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader><TableRow><TableHead>Ad Soyad</TableHead><TableHead>Sınıf</TableHead><TableHead>Veli</TableHead><TableHead>Öğretmen</TableHead><TableHead>Borç</TableHead><TableHead>İşlem</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {students.map(s => {
                        const t = teachers.find(t => t.id === s.ogretmen_id);
                        return (
                          <TableRow key={s.id}>
                            <TableCell className="font-medium">{s.ad} {s.soyad}</TableCell>
                            <TableCell>{s.sinif}</TableCell>
                            <TableCell>{s.veli_ad} {s.veli_soyad}</TableCell>
                            <TableCell>{t ? `${t.ad} ${t.soyad}` : '-'}</TableCell>
                            <TableCell className="text-green-600 font-semibold">{formatCurrency(Math.max(0, s.yapilmasi_gereken_odeme - s.yapilan_odeme))}</TableCell>
                            <TableCell><div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => { setEditingItem({type:'student',data:s}); setEditDialogOpen(true); }}><Edit2 className="h-4 w-4" /></Button><Button variant="destructive" size="sm" onClick={() => deleteStudent(s.id)}><Trash2 className="h-4 w-4" /></Button></div></TableCell>
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
                <CardHeader><CardTitle>Kurslar</CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader><TableRow><TableHead>Kurs Adı</TableHead><TableHead>Fiyat</TableHead><TableHead>Süre</TableHead><TableHead>İşlem</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {courses.map(c => (
                        <TableRow key={c.id}>
                          <TableCell className="font-medium">{c.ad}</TableCell>
                          <TableCell>{formatCurrency(c.fiyat)}</TableCell>
                          <TableCell>{c.sure} saat</TableCell>
                          <TableCell><div className="flex gap-2"><Button variant="outline" size="sm" onClick={() => { setEditingItem({type:'course',data:c}); setEditDialogOpen(true); }}><Edit2 className="h-4 w-4" /></Button><Button variant="destructive" size="sm" onClick={() => deleteCourse(c.id)}><Trash2 className="h-4 w-4" /></Button></div></TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Payments */}
          <TabsContent value="payments">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <Card className="lg:col-span-1 border-0 shadow-sm">
                <CardHeader><CardTitle className="flex items-center gap-2"><Plus className="h-5 w-5" />Yeni Ödeme</CardTitle></CardHeader>
                <CardContent>
                  <form onSubmit={createPayment} className="space-y-4">
                    <div><Label>Tip</Label>
                      <Select value={paymentForm.tip} onValueChange={v => setPaymentForm({...paymentForm, tip:v})}>
                        <SelectTrigger><SelectValue /></SelectTrigger>
                        <SelectContent><SelectItem value="ogrenci">Öğrenci</SelectItem><SelectItem value="ogretmen">Öğretmen</SelectItem></SelectContent>
                      </Select>
                    </div>
                    <div><Label>{paymentForm.tip === 'ogrenci' ? 'Öğrenci' : 'Öğretmen'}</Label>
                      <Select value={paymentForm.kisi_id} onValueChange={v => setPaymentForm({...paymentForm, kisi_id:v})}>
                        <SelectTrigger><SelectValue placeholder="Seçin" /></SelectTrigger>
                        <SelectContent>{(paymentForm.tip === 'ogrenci' ? students : teachers).map(p => <SelectItem key={p.id} value={p.id}>{p.ad} {p.soyad}</SelectItem>)}</SelectContent>
                      </Select>
                    </div>
                    <div><Label>Miktar (₺)</Label><Input type="number" step="0.01" value={paymentForm.miktar} onChange={e => setPaymentForm({...paymentForm, miktar:parseFloat(e.target.value)||0})} required /></div>
                    <div><Label>Açıklama</Label><Input value={paymentForm.aciklama} onChange={e => setPaymentForm({...paymentForm, aciklama:e.target.value})} /></div>
                    <Button type="submit" disabled={loadingAction} className="w-full">Ekle</Button>
                  </form>
                </CardContent>
              </Card>
              <Card className="lg:col-span-2 border-0 shadow-sm">
                <CardHeader><CardTitle>Ödemeler</CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader><TableRow><TableHead>Tarih</TableHead><TableHead>Tip</TableHead><TableHead>Kişi</TableHead><TableHead>Miktar</TableHead><TableHead>Açıklama</TableHead></TableRow></TableHeader>
                    <TableBody>
                      {payments.map(p => {
                        const person = p.tip === 'ogrenci' ? students.find(s => s.id === p.kisi_id) : teachers.find(t => t.id === p.kisi_id);
                        return (
                          <TableRow key={p.id}>
                            <TableCell>{formatDate(p.tarih)}</TableCell>
                            <TableCell><Badge variant={p.tip === 'ogrenci' ? 'default' : 'secondary'}>{p.tip === 'ogrenci' ? 'Öğrenci' : 'Öğretmen'}</Badge></TableCell>
                            <TableCell>{person ? `${person.ad} ${person.soyad}` : '-'}</TableCell>
                            <TableCell className="font-semibold text-green-600">{formatCurrency(p.miktar)}</TableCell>
                            <TableCell>{p.aciklama || '-'}</TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Users - admin only */}
          {user.role === "admin" && (
            <TabsContent value="users">
              <UserManagement teachers={teachers} />
            </TabsContent>
          )}
        </Tabs>

          {/* Gelisim Alani */}
          <TabsContent value="gelisim">
            <GelisimAlani user={user} />
          </TabsContent>

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
      </div>
      <Toaster />
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
  const [adminForm, setAdminForm] = useState({ baslik: "", tur: "hizmetici", aciklama: "", hedef_kitle: "hepsi", sorular: [] });
  const [yeniSoru, setYeniSoru] = useState({ soru: "", secenekler: ["", "", "", ""], dogru_cevap: 0 });

  const fetchAll = useCallback(async () => {
    try { const r = await axios.get(`${API}/gelisim/icerik`); setIcerikler(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/gelisim/tamamlama/${user.id}`); setTamamlananlar(r.data); } catch(e) {}
    try { const r = await axios.get(`${API}/gelisim/puan-tablosu`); setPuanTablosu(r.data); } catch(e) {}
  }, [user.id]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const turIcon = (tur) => ({ hizmetici: <GraduationCap className="h-5 w-5"/>, film: <Film className="h-5 w-5"/>, kitap: <BookMarked className="h-5 w-5"/> }[tur] || <BookOpen className="h-5 w-5"/>);
  const turLabel = (tur) => ({ hizmetici: "Hizmetiçi Eğitim", film: "Film", kitap: "Kitap" }[tur] || tur);
  const turColor = (tur) => ({ hizmetici: "bg-blue-100 text-blue-600", film: "bg-purple-100 text-purple-600", kitap: "bg-green-100 text-green-600" }[tur] || "bg-gray-100 text-gray-600");
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

  const adminKarar = async (icerikId, onay) => {
    try {
      await axios.post(`${API}/gelisim/icerik/${icerikId}/admin-karar`, { onay });
      toast({ title: onay ? "Oylama başlatıldı" : "İçerik reddedildi" });
      fetchAll();
    } catch(e) { toast({ title: "Hata", variant: "destructive" }); }
  };

  const oyVer = async (onay, sebep = "") => {
    if (!onay && !sebep) { setRedDialogIcerik(aktifIcerik || redDialogIcerik); return; }
    try {
      const r = await axios.post(`${API}/gelisim/oy`, { icerik_id: (aktifIcerik || redDialogIcerik).id, onay, sebep });
      toast({ title: onay ? `✅ Onaylandı (+2 puan)` : "❌ Reddedildi", description: `Onay oranı: %${r.data.onay_orani}` });
      setRedDialogIcerik(null); setRedSebep(""); fetchAll();
    } catch(e) { toast({ title: "Hata", description: e.response?.data?.detail || "Hata", variant: "destructive" }); }
  };

  const handleTamamla = async (testYapildi) => {
    try {
      const data = { icerik_id: aktifIcerik.id, kullanici_id: user.id };
      if (testYapildi) data.test_cevaplari = testCevaplari;
      const r = await axios.post(`${API}/gelisim/tamamla`, data);
      setSonuc(r.data); setGorunum("sonuc"); fetchAll();
      toast({ title: `+${r.data.puan} puan kazandınız!` });
    } catch(e) { toast({ title: "Hata", description: e.response?.data?.detail, variant: "destructive" }); }
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
      setAdminForm({ baslik: "", tur: "hizmetici", aciklama: "", hedef_kitle: "hepsi", sorular: [] });
      setGorunum("liste"); fetchAll();
      toast({ title: user.role === "admin" ? "İçerik oylama aşamasına alındı" : "İçerik yönetici onayına gönderildi" });
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
          Testi Tamamla ({testCevaplari.filter(c=>c!==undefined).length}/{aktifIcerik.sorular.length} cevaplandı)
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
                    <SelectContent>
                      <SelectItem value="hizmetici">📚 Hizmetiçi Eğitim</SelectItem>
                      <SelectItem value="film">🎬 Film</SelectItem>
                      <SelectItem value="kitap">📖 Kitap</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div><Label>Hedef Kitle</Label>
                  <Select value={adminForm.hedef_kitle} onValueChange={v => setAdminForm({...adminForm, hedef_kitle: v})}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="hepsi">👥 Herkes</SelectItem>
                      <SelectItem value="ogretmen">👩‍🏫 Öğretmenler</SelectItem>
                      <SelectItem value="ogrenci">🎓 Öğrenciler</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div><Label>Açıklama</Label><Input value={adminForm.aciklama} onChange={e => setAdminForm({...adminForm, aciklama: e.target.value})} placeholder="Kısa açıklama..." /></div>

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
                  {user.role === "admin" ? "Oylama Başlat" : "Yöneticiye Gönder"}
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
          {user.role === "admin" && bekleyenler.length > 0 && (
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
                      <div className="flex gap-2">
                        <Button size="sm" onClick={() => adminKarar(icerik.id, true)} className="bg-green-600 hover:bg-green-700 text-white">✅ Oylama Başlat</Button>
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
                            <Button size="sm" onClick={() => oyVer(true)} className="bg-green-600 hover:bg-green-700 text-white flex-1">✅ Onayla (+2 puan)</Button>
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
                            {user.role === "admin" && <Button variant="destructive" size="sm" onClick={async () => { try { await axios.delete(`${API}/gelisim/icerik/${icerik.id}`); fetchAll(); toast({title:"Silindi"}); } catch(e){} }}><Trash2 className="h-4 w-4"/></Button>}
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
