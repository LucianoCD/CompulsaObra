import React, { useEffect, useRef, useState } from 'react';
import { useWorkspaceStore } from '../store/useWorkspaceStore';
import {
  Lock,
  Mail,
  User,
  Building2,
  X,
  AlertCircle,
  Loader2,
  CheckCircle2,
  RefreshCw,
  KeyRound,
} from 'lucide-react';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

type AuthStep = 'login' | 'register' | 'verify';

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose }) => {
  const [step, setStep] = useState<AuthStep>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [workspaceName, setWorkspaceName] = useState('');
  const [verificationCode, setVerificationCode] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    login,
    register,
    verifyEmail,
    resendVerification,
    pendingVerificationEmail,
    clearPendingVerification,
  } = useWorkspaceStore();
  const dialogRef = useRef<HTMLDialogElement | null>(null);

  useEffect(() => {
    if (isOpen && dialogRef.current) {
      if (!dialogRef.current.open) dialogRef.current.showModal();
    } else if (!isOpen && dialogRef.current?.open) {
      dialogRef.current.close();
    }
  }, [isOpen]);

  useEffect(() => {
    if (pendingVerificationEmail && !email) {
      setEmail(pendingVerificationEmail);
    }
  }, [pendingVerificationEmail, email]);

  if (!isOpen) return null;

  const handleClose = () => {
    clearPendingVerification();
    setStep('login');
    setVerificationCode('');
    setPassword('');
    setFormError(null);
    setInfoMessage(null);
    onClose();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setInfoMessage(null);
    setIsSubmitting(true);

    try {
      if (step === 'register') {
        if (!fullName.trim()) {
          throw new Error('Por favor ingresá tu nombre completo.');
        }
        const res = await register(
          email.trim(),
          password,
          fullName.trim(),
          workspaceName.trim() || undefined
        );
        if (res.authenticated && !res.verification_required) {
          handleClose();
        } else {
          setInfoMessage(
            res.message ||
              'Te enviamos un correo con el código de verificación para activar tu cuenta.'
          );
          setStep('verify');
        }
      } else if (step === 'verify') {
        if (!verificationCode.trim()) {
          throw new Error('Ingresá el código de verificación recibido por correo.');
        }
        await verifyEmail(email.trim(), verificationCode.trim());
        handleClose();
      } else {
        await login(email.trim(), password);
        handleClose();
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error de autenticación';
      setFormError(msg);
      if (
        step === 'login' &&
        msg.toLowerCase().includes('verificar su correo')
      ) {
        setStep('verify');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResend = async () => {
    if (!email.trim()) {
      setFormError('Ingresá tu correo electrónico para reenviar la verificación.');
      return;
    }
    setFormError(null);
    setInfoMessage(null);
    setIsSubmitting(true);
    try {
      const msg = await resendVerification(email.trim());
      setInfoMessage(msg);
    } catch (err: unknown) {
      setFormError(
        err instanceof Error ? err.message : 'No se pudo reenviar el correo'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="auth-modal-title"
      onClose={handleClose}
      className="fixed inset-0 m-auto w-full max-w-md bg-surface-elevated border border-surface-hairline rounded-container shadow-modal p-0 text-content-primary backdrop:bg-black/50 backdrop:backdrop-blur-sm focus:outline-none"
    >
      <div className="p-6 relative">
        <button
          onClick={handleClose}
          type="button"
          className="absolute top-4 right-4 text-content-muted hover:text-content-primary p-2 rounded-control hover:bg-surface-subtle transition"
          aria-label="Cerrar ventana"
        >
          <X className="w-4 h-4" />
        </button>

        <div className="mb-5 pr-8">
          <span className="text-xs font-bold uppercase tracking-wide text-action-primary">
            Acceso a tu Espacio de Trabajo
          </span>
          <h2
            id="auth-modal-title"
            className="text-lg font-bold text-content-primary font-display mt-0.5"
          >
            {step === 'register'
              ? 'Crear Cuenta de Presupuestador'
              : step === 'verify'
                ? 'Verificar Correo Electrónico'
                : 'Iniciar Sesión'}
          </h2>
          <p className="text-[13px] text-content-secondary mt-1 leading-snug">
            {step === 'verify'
              ? 'Confirmá tu dirección de correo con el código enviado para habilitar tu espacio privado.'
              : 'Guardá tus propios corralones, listas de precios y presupuestos en un espacio privado.'}
          </p>
        </div>

        {formError && (
          <div
            role="alert"
            className="mb-4 p-3 rounded-control bg-semantic-dangerBg border border-semantic-dangerBorder flex items-start gap-2.5 text-[13px] text-semantic-dangerText font-medium"
          >
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{formError}</span>
          </div>
        )}

        {infoMessage && (
          <div
            role="status"
            className="mb-4 p-3 rounded-control bg-semantic-winnerBg border border-emerald-600/30 flex items-start gap-2.5 text-[13px] text-semantic-winnerText font-medium"
          >
            <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{infoMessage}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3.5">
          {step === 'register' && (
            <>
              <div>
                <label
                  htmlFor="auth-fullname"
                  className="block text-[13px] font-semibold text-content-secondary mb-1"
                >
                  Nombre Completo
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-content-muted absolute left-3 top-3" />
                  <input
                    id="auth-fullname"
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Ej. Ing. Juan Pérez"
                    className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control pl-9 pr-3 text-[13px] text-content-primary focus:border-surface-strong"
                  />
                </div>
              </div>

              <div>
                <label
                  htmlFor="auth-workspace"
                  className="block text-[13px] font-semibold text-content-secondary mb-1"
                >
                  Nombre de tu Constructora o Estudio (Opcional)
                </label>
                <div className="relative">
                  <Building2 className="w-4 h-4 text-content-muted absolute left-3 top-3" />
                  <input
                    id="auth-workspace"
                    type="text"
                    value={workspaceName}
                    onChange={(e) => setWorkspaceName(e.target.value)}
                    placeholder="Ej. Pérez & Asoc. Construcciones"
                    className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control pl-9 pr-3 text-[13px] text-content-primary focus:border-surface-strong"
                  />
                </div>
              </div>
            </>
          )}

          <div>
            <label
              htmlFor="auth-email"
              className="block text-[13px] font-semibold text-content-secondary mb-1"
            >
              Correo Electrónico
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-content-muted absolute left-3 top-3" />
              <input
                id="auth-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="juan@constructora.com"
                className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control pl-9 pr-3 text-[13px] text-content-primary focus:border-surface-strong font-mono"
              />
            </div>
          </div>

          {step !== 'verify' && (
            <div>
              <label
                htmlFor="auth-password"
                className="block text-[13px] font-semibold text-content-secondary mb-1"
              >
                Contraseña
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-content-muted absolute left-3 top-3" />
                <input
                  id="auth-password"
                  type="password"
                  required
                  minLength={6}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control pl-9 pr-3 text-[13px] text-content-primary focus:border-surface-strong"
                />
              </div>
            </div>
          )}

          {step === 'verify' && (
            <div>
              <label
                htmlFor="auth-verify-code"
                className="block text-[13px] font-semibold text-content-secondary mb-1"
              >
                Código de Verificación
              </label>
              <div className="relative">
                <KeyRound className="w-4 h-4 text-content-muted absolute left-3 top-3" />
                <input
                  id="auth-verify-code"
                  type="text"
                  required
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value)}
                  placeholder="Pegá el código recibido por correo"
                  className="w-full h-10 bg-surface-subtle border border-surface-hairline rounded-control pl-9 pr-3 text-[13px] text-content-primary focus:border-surface-strong font-mono"
                />
              </div>
            </div>
          )}

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 px-4 rounded-control bg-action-primary hover:bg-action-hover disabled:opacity-55 text-action-primaryFg font-bold text-[13px] shadow-card transition flex items-center justify-center gap-2 min-h-[44px]"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Procesando...</span>
              </>
            ) : step === 'register' ? (
              'Crear Cuenta y Enviar Verificación'
            ) : step === 'verify' ? (
              'Confirmar Correo y Entrar'
            ) : (
              'Iniciar Sesión'
            )}
          </button>

          {step === 'verify' && (
            <button
              type="button"
              disabled={isSubmitting}
              onClick={handleResend}
              className="w-full py-2 px-3 rounded-control bg-surface-subtle hover:bg-surface-canvas border border-surface-hairline text-[13px] font-semibold text-content-secondary hover:text-content-primary transition flex items-center justify-center gap-1.5 min-h-[40px]"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Reenviar correo de verificación</span>
            </button>
          )}
        </form>

        <div className="mt-4 pt-4 border-t border-surface-hairline flex flex-col gap-2">
          {step !== 'verify' && (
            <button
              type="button"
              onClick={() => {
                setStep(step === 'register' ? 'login' : 'register');
                setFormError(null);
                setInfoMessage(null);
              }}
              className="text-[13px] text-content-secondary hover:text-action-primary transition text-center font-semibold"
            >
              {step === 'register'
                ? '¿Ya tienes cuenta? Inicia sesión aquí'
                : '¿No tienes cuenta? Regístrate gratis'}
            </button>
          )}

          <button
            type="button"
            onClick={() => {
              setStep(step === 'verify' ? 'login' : 'verify');
              setFormError(null);
            }}
            className="text-xs text-content-muted hover:text-action-primary transition text-center font-medium"
          >
            {step === 'verify'
              ? 'Volver a Iniciar Sesión'
              : '¿Ya tenés un código de verificación? Ingresarlo aquí'}
          </button>
        </div>
      </div>
    </dialog>
  );
};
