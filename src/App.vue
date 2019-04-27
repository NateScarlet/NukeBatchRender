<template lang="pug">
  #app
    img(src='@/assets/logo.png')
    div
      p
        | If Element is successfully added to this project, you'll see an
        code(v-text="'<el-button>'")
        | below
      ElButton el-button
    HelloWorld(msg="Welcome to Your Vue.js App")
</template>

<script lang="ts">
import { Component, Vue } from 'vue-property-decorator';
import HelloWorld from '@/components/HelloWorld.vue';

@Component<App>({
  name: 'app',
  components: { HelloWorld }
})
export default class App extends Vue {}
</script>

<style>
#app {
  font-family: 'Avenir', Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  margin-top: 60px;
}
</style>
