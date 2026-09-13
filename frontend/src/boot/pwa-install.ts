import { defineBoot } from '#q-app/wrappers';
import { registraAscoltatoriInstall } from 'src/composables/useInstallPwa';

/**
 * `beforeinstallprompt` arriva all'avvio dell'app, prima che la rotta
 * `/installa` (lazy) sia montata: va intercettato qui e messo da parte, o
 * il bottone "Installa" non si abilita mai su un caricamento a freddo.
 */
export default defineBoot(() => {
  registraAscoltatoriInstall();
});
