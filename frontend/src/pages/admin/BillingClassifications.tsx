import React, { useState, useEffect } from 'react';
import {
  listBillingClassifications,
  createBillingClassification,
  updateBillingClassification,
  deleteBillingClassification,
} from '../../api/client';
import { PlusCircle, Edit2, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import Topbar from '../../components/Topbar';
import Card from '../../components/Card';
import LoadingState from '../../components/LoadingState';

type SortField = 'category' | 'hsn' | 'gst' | 'status';
type SortDir = 'asc' | 'desc';

export function BillingClassifications() {
  const [classifications, setClassifications] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [sortField, setSortField] = useState<SortField>('category');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    category: '',
    description: '',
    item_type: 'SERVICE',
    hsn_sac_code: '',
    hsn_sac_type: 'SAC',
    gst_rate: 18.0,
    keywords: '',
    active: true
  });

  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchClassifications();
  }, []);

  const fetchClassifications = async () => {
    try {
      setLoading(true);
      const data = await listBillingClassifications();
      setClassifications(data);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load classifications');
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingId(null);
    setFieldErrors({});
    setFormData({
      category: '',
      description: '',
      item_type: 'SERVICE',
      hsn_sac_code: '',
      hsn_sac_type: 'SAC',
      gst_rate: 18.0,
      keywords: '',
      active: true
    });
    setShowModal(true);
  };

  const openEditModal = (c: any) => {
    setEditingId(c.id);
    setFieldErrors({});
    setFormData({
      category: c.category,
      description: c.description,
      item_type: c.item_type,
      hsn_sac_code: c.hsn_sac_code,
      hsn_sac_type: c.hsn_sac_type,
      gst_rate: parseFloat(c.gst_rate),
      keywords: c.keywords || '',
      active: c.active
    });
    setShowModal(true);
  };

  const validate = (): Record<string, string> => {
    const errors: Record<string, string> = {};
    if (!formData.category.trim()) errors.category = 'Category is required';
    else if (formData.category.length > 100) errors.category = 'Must be 100 characters or fewer';
    if (!formData.description.trim()) errors.description = 'Description is required';
    if (!formData.hsn_sac_code.trim()) errors.hsn_sac_code = 'HSN/SAC code is required';
    else if (formData.hsn_sac_code.length > 50) errors.hsn_sac_code = 'Must be 50 characters or fewer';
    if (Number.isNaN(formData.gst_rate) || formData.gst_rate === null || formData.gst_rate === undefined) {
      errors.gst_rate = 'GST rate is required';
    } else if (formData.gst_rate < 0 || formData.gst_rate > 100) {
      errors.gst_rate = 'Must be between 0 and 100';
    }
    return errors;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) {
      toast.error('Please fix the highlighted fields');
      return;
    }
    try {
      if (editingId) {
        await updateBillingClassification(editingId, formData);
        toast.success('Classification updated');
      } else {
        await createBillingClassification(formData);
        toast.success('Classification created');
      }
      setShowModal(false);
      fetchClassifications();
    } catch (err: any) {
      toast.error(err.message || 'Save failed');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to disable this classification?')) return;
    try {
      await deleteBillingClassification(id);
      toast.success('Disabled successfully');
      fetchClassifications();
    } catch (err: any) {
      toast.error(err.message || 'Delete failed');
    }
  };

  const visibleClassifications = classifications.filter((c) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      (c.category || '').toLowerCase().includes(q) ||
      (c.description || '').toLowerCase().includes(q) ||
      (c.hsn_sac_code || '').toLowerCase().includes(q)
    );
  }).sort((a, b) => {
    let cmp = 0;
    if (sortField === 'category') {
      cmp = (a.category || '').localeCompare(b.category || '');
      if (cmp === 0) {
        cmp = (a.description || '').localeCompare(b.description || '');
      }
    } else if (sortField === 'hsn') {
      cmp = (a.hsn_sac_code || '').localeCompare(b.hsn_sac_code || '');
    } else if (sortField === 'gst') {
      cmp = parseFloat(a.gst_rate) - parseFloat(b.gst_rate);
    } else if (sortField === 'status') {
      cmp = (a.active === b.active) ? 0 : a.active ? -1 : 1;
    }
    return sortDir === 'asc' ? cmp : -cmp;
  });

  function handleSort(field: SortField) {
    if (sortField === field) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDir('asc');
    }
  }

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <span className="ml-1 text-slate-300">↕</span>;
    return <span className="ml-1 text-brand-500">{sortDir === 'asc' ? '↑' : '↓'}</span>;
  };

  return (
    <div className="flex-1 bg-transparent min-h-screen">
      <Topbar
        title="Billing Classifications"
        subtitle="Catalog of billable items (HSN/SAC) used to auto-classify invoice line items."
      >
        <button
          onClick={openCreateModal}
          className="text-sm font-medium bg-brand-600 text-white px-4 py-2.5 rounded-full hover:bg-brand-700 inline-flex items-center gap-2 transition-colors"
        >
          <PlusCircle className="w-4 h-4" />
          Add Classification
        </button>
      </Topbar>

      <div className="p-4 sm:p-8">
        <div className="space-y-6">

          {/* Catalog Table */}
          <Card className="!p-0 overflow-hidden">
            <div className="p-4 border-b border-slate-100">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search by category, description, or HSN/SAC code…"
                className="w-full sm:w-80 border border-slate-200 rounded-full px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm whitespace-nowrap">
                <thead className="bg-slate-50 text-slate-400 text-xs uppercase tracking-wider border-b border-slate-100">
                  <tr>
                    <th className="px-5 py-3 font-medium cursor-pointer hover:text-slate-600 transition-colors" onClick={() => handleSort('category')}>
                      Category / Description <SortIcon field="category" />
                    </th>
                    <th className="px-5 py-3 font-medium cursor-pointer hover:text-slate-600 transition-colors" onClick={() => handleSort('hsn')}>
                      HSN/SAC <SortIcon field="hsn" />
                    </th>
                    <th className="px-5 py-3 font-medium text-right cursor-pointer hover:text-slate-600 transition-colors" onClick={() => handleSort('gst')}>
                      GST % <SortIcon field="gst" />
                    </th>
                    <th className="px-5 py-3 font-medium text-center cursor-pointer hover:text-slate-600 transition-colors" onClick={() => handleSort('status')}>
                      Status <SortIcon field="status" />
                    </th>
                    <th className="px-5 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading ? (
                    <tr><td colSpan={5}><LoadingState className="py-6" /></td></tr>
                  ) : classifications.length === 0 ? (
                    <tr><td colSpan={5} className="px-5 py-10 text-center text-slate-400">No classifications found</td></tr>
                  ) : visibleClassifications.length === 0 ? (
                    <tr><td colSpan={5} className="px-5 py-10 text-center text-slate-400">No classifications match "{search}"</td></tr>
                  ) : (
                    visibleClassifications.map((c) => (
                      <tr key={c.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-5 py-3.5">
                          <div className="font-medium text-slate-800">{c.category}</div>
                          <div className="text-slate-400 text-xs truncate max-w-[300px]" title={c.description}>{c.description}</div>
                        </td>
                        <td className="px-5 py-3.5 font-mono text-slate-600">{c.hsn_sac_code} <span className="text-xs text-slate-400">({c.hsn_sac_type})</span></td>
                        <td className="px-5 py-3.5 text-right font-medium text-slate-700">{parseFloat(c.gst_rate)}%</td>
                        <td className="px-5 py-3.5 text-center">
                          {c.active ?
                            <span className="text-xs font-medium text-brand-700 bg-brand-50 px-2.5 py-1 rounded-full">Active</span> :
                            <span className="text-xs font-medium text-coral-600 bg-coral-50 px-2.5 py-1 rounded-full">Disabled</span>
                          }
                        </td>
                        <td className="px-5 py-3.5 text-right">
                          <button onClick={() => openEditModal(c)} className="text-slate-400 hover:text-brand-600 p-1.5 rounded-full hover:bg-brand-50 transition-colors"><Edit2 className="w-4 h-4" /></button>
                          {c.active && (
                            <button onClick={() => handleDelete(c.id)} className="text-slate-400 hover:text-coral-600 p-1.5 rounded-full hover:bg-coral-50 ml-1 transition-colors"><Trash2 className="w-4 h-4" /></button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </Card>

        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-[2px] p-4">
          <div className="bg-white rounded-3xl shadow-card w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-semibold tracking-tight text-slate-900 mb-4">{editingId ? 'Edit Classification' : 'New Classification'}</h2>
            <form onSubmit={handleSubmit} className="space-y-4">

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Category <span className="text-coral-500">*</span></label>
                  <input
                    required
                    type="text"
                    maxLength={100}
                    className={`w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 ${fieldErrors.category ? 'border-coral-300 focus:ring-coral-200' : 'border-slate-200 focus:ring-brand-300'}`}
                    value={formData.category}
                    onChange={(e) => { setFormData({...formData, category: e.target.value}); setFieldErrors(prev => ({...prev, category: ''})) }}
                    placeholder="e.g. Software Development"
                  />
                  {fieldErrors.category && <p className="text-xs text-coral-600 mt-1">{fieldErrors.category}</p>}
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Item Type <span className="text-coral-500">*</span></label>
                  <select className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300" value={formData.item_type} onChange={(e) => setFormData({...formData, item_type: e.target.value})}>
                    <option value="SERVICE">Service</option>
                    <option value="HARDWARE">Hardware</option>
                    <option value="SOFTWARE">Software License</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Description (Internal / Display Name) <span className="text-coral-500">*</span></label>
                <input
                  required
                  type="text"
                  className={`w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 ${fieldErrors.description ? 'border-coral-300 focus:ring-coral-200' : 'border-slate-200 focus:ring-brand-300'}`}
                  value={formData.description}
                  onChange={(e) => { setFormData({...formData, description: e.target.value}); setFieldErrors(prev => ({...prev, description: ''})) }}
                  placeholder="e.g. Custom backend development services"
                />
                {fieldErrors.description && <p className="text-xs text-coral-600 mt-1">{fieldErrors.description}</p>}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">Type <span className="text-coral-500">*</span></label>
                  <select className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-300" value={formData.hsn_sac_type} onChange={(e) => setFormData({...formData, hsn_sac_type: e.target.value})}>
                    <option value="SAC">SAC</option>
                    <option value="HSN">HSN</option>
                  </select>
                </div>
                <div>
                  <label className="flex items-baseline justify-between text-xs font-medium text-slate-500 mb-1">
                    <span>HSN/SAC Code <span className="text-coral-500">*</span></span>
                    <span className="text-slate-300 font-normal">{formData.hsn_sac_code.length}/50</span>
                  </label>
                  <input
                    required
                    type="text"
                    maxLength={50}
                    className={`w-full border rounded-xl px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 ${fieldErrors.hsn_sac_code ? 'border-coral-300 focus:ring-coral-200' : 'border-slate-200 focus:ring-brand-300'}`}
                    value={formData.hsn_sac_code}
                    onChange={(e) => { setFormData({...formData, hsn_sac_code: e.target.value}); setFieldErrors(prev => ({...prev, hsn_sac_code: ''})) }}
                    placeholder="e.g. 998314"
                  />
                  {fieldErrors.hsn_sac_code && <p className="text-xs text-coral-600 mt-1">{fieldErrors.hsn_sac_code}</p>}
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-500 mb-1">GST Rate (%) <span className="text-coral-500">*</span></label>
                  <input
                    required
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    className={`w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 ${fieldErrors.gst_rate ? 'border-coral-300 focus:ring-coral-200' : 'border-slate-200 focus:ring-brand-300'}`}
                    value={formData.gst_rate}
                    onChange={(e) => { setFormData({...formData, gst_rate: parseFloat(e.target.value)}); setFieldErrors(prev => ({...prev, gst_rate: ''})) }}
                  />
                  {fieldErrors.gst_rate ? (
                    <p className="text-xs text-coral-600 mt-1">{fieldErrors.gst_rate}</p>
                  ) : (
                    <p className="text-xs text-slate-400 mt-1">A number between 0 and 100</p>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">Matcher Keywords (comma separated)</label>
                <input type="text" className="w-full border border-slate-200 rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300" value={formData.keywords} onChange={(e) => setFormData({...formData, keywords: e.target.value})} placeholder="e.g. api, integration, backend, nodejs" />
                <p className="text-xs text-slate-400 mt-1">These words increase the confidence score during auto-matching. Optional.</p>
              </div>

              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" id="active" className="rounded text-brand-600 focus:ring-brand-400" checked={formData.active} onChange={(e) => setFormData({...formData, active: e.target.checked})} />
                <span className="text-sm font-medium text-slate-700">Active (available for matching and selection)</span>
              </label>

              <div className="pt-4 flex flex-wrap justify-end gap-3 border-t border-slate-100">
                <button type="button" onClick={() => setShowModal(false)} className="px-5 py-2.5 rounded-full text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors">Cancel</button>
                <button type="submit" className="px-5 py-2.5 rounded-full text-sm font-medium bg-brand-600 text-white hover:bg-brand-700 transition-colors">Save Classification</button>
              </div>

            </form>
          </div>
        </div>
      )}
    </div>
  );
}
