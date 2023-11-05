﻿using AssetStudio;
using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

namespace AssetStudioGUI
{
    internal static class Exporter
    {
        public static bool ExportTexture2D(AssetItem item, string exportPath)
        {
            var m_Texture2D = (Texture2D)item.Asset;
            if (Properties.Settings.Default.convertTexture)
            {
                var type = Properties.Settings.Default.convertType;
                if (!TryExportFile(exportPath, item, "." + type.ToString().ToLower(), out var exportFullPath))
                    return false;
                var image = m_Texture2D.ConvertToImage(true);
                if (image == null)
                    return false;
                using (image)
                {
                    using (var file = File.OpenWrite(exportFullPath))
                    {
                        image.WriteToStream(file, type);  
                    }
                    return true;
                }
            }
            else
            {
                if (!TryExportFile(exportPath, item, ".tex", out var exportFullPath))
                    return false;
                File.WriteAllBytes(exportFullPath, m_Texture2D.image_data.GetData());
                return true;
            }
        }

        public static bool ExportAudioClip(AssetItem item, string exportPath)
        {
            var m_AudioClip = (AudioClip)item.Asset;
            var m_AudioData = m_AudioClip.m_AudioData.GetData();
            if (m_AudioData == null || m_AudioData.Length == 0)
                return false;
            var converter = new AudioClipConverter(m_AudioClip);
            if (Properties.Settings.Default.convertAudio && converter.IsSupport)
            {
                if (!TryExportFile(exportPath, item, ".wav", out var exportFullPath))
                    return false;
                var buffer = converter.ConvertToWav();
                if (buffer == null)
                    return false;
                File.WriteAllBytes(exportFullPath, buffer);
            }
            else
            {
                if (!TryExportFile(exportPath, item, converter.GetExtensionName(), out var exportFullPath))
                    return false;
                File.WriteAllBytes(exportFullPath, m_AudioData);
            }
            return true;
        }

        public static bool ExportShader(AssetItem item, string exportPath)
        {
            if (!TryExportFile(exportPath, item, ".shader", out var exportFullPath))
                return false;
            var m_Shader = (Shader)item.Asset;
            var str = m_Shader.Convert(Studio.Game);
            File.WriteAllText(exportFullPath, str);
            return true;
        }

        public static bool ExportTextAsset(AssetItem item, string exportPath)
        {
            var m_TextAsset = (TextAsset)(item.Asset);
            var extension = ".txt";
            if (Properties.Settings.Default.restoreExtensionName)
            {
                if (!string.IsNullOrEmpty(item.Container))
                {
                    extension = Path.GetExtension(item.Container);
                }
            }
            if (!TryExportFile(exportPath, item, extension, out var exportFullPath))
                return false;
            File.WriteAllBytes(exportFullPath, m_TextAsset.m_Script);
            return true;
        }

        public static bool ExportMonoBehaviour(AssetItem item, string exportPath)
        {
            var m_MonoBehaviour = (MonoBehaviour)item.Asset;
            String name = m_MonoBehaviour.m_Name;
            if (name.EndsWith("_Atlas"))
            {
                if (!TryExportFile(exportPath, item, ".atlas", out var exportFullPath))
                    return false;
                String data = System.Text.Encoding.UTF8.GetString(m_MonoBehaviour.GetRawData());
                String split_identify = name.Replace("_Atlas", ".png");
                // TODO 使用FOR循环列表切片
                String rawAtlasData = split_identify + data.Split(split_identify)[1];
                File.WriteAllText(exportFullPath, rawAtlasData);
            }
            else
            {
                if (!TryExportFile(exportPath, item, ".json", out var exportFullPath))
                    return false;
                var type = m_MonoBehaviour.ToType();
                if (type == null)
                {
                    var m_Type = Studio.MonoBehaviourToTypeTree(m_MonoBehaviour);
                    type = m_MonoBehaviour.ToType(m_Type);
                }
                var str = JsonConvert.SerializeObject(type, Formatting.Indented);
                File.WriteAllText(exportFullPath, str);
            }
            return true;
        }

        public static bool ExportMiHoYoBinData(AssetItem item, string exportPath)
        {
            string exportFullPath;
            if (item.Asset is MiHoYoBinData m_MiHoYoBinData)
            {
                switch (m_MiHoYoBinData.Type)
                {
                    case MiHoYoBinDataType.JSON:
                        if (!TryExportFile(exportPath, item, ".json", out exportFullPath))
                            return false;
                        var json = m_MiHoYoBinData.Dump() as string;
                        if (json.Length != 0)
                        {
                            File.WriteAllText(exportFullPath, json);
                            return true;
                        }
                        break;
                    case MiHoYoBinDataType.Bytes:
                        if (!TryExportFile(exportPath, item, ".bin", out exportFullPath))
                            return false;
                        var bytes = m_MiHoYoBinData.Dump() as byte[];
                        if (bytes.Length != 0)
                        {
                            File.WriteAllBytes(exportFullPath, bytes);
                            return true;
                        }
                        break;
                }
            }
            return false;
        }

        public static bool ExportFont(AssetItem item, string exportPath)
        {
            var m_Font = (Font)item.Asset;
            if (m_Font.m_FontData != null)
            {
                var extension = ".ttf";
                if (m_Font.m_FontData[0] == 79 && m_Font.m_FontData[1] == 84 && m_Font.m_FontData[2] == 84 && m_Font.m_FontData[3] == 79)
                {
                    extension = ".otf";
                }
                if (!TryExportFile(exportPath, item, extension, out var exportFullPath))
                    return false;
                File.WriteAllBytes(exportFullPath, m_Font.m_FontData);
                return true;
            }
            return false;
        }

        public static bool ExportMesh(AssetItem item, string exportPath)
        {
            var m_Mesh = (Mesh)item.Asset;
            if (m_Mesh.m_VertexCount <= 0)
                return false;
            if (!TryExportFile(exportPath, item, ".obj", out var exportFullPath))
                return false;
            var sb = new StringBuilder();
            sb.AppendLine("g " + m_Mesh.m_Name);
            #region Vertices
            if (m_Mesh.m_Vertices == null || m_Mesh.m_Vertices.Length == 0)
            {
                return false;
            }
            int c = 3;
            if (m_Mesh.m_Vertices.Length == m_Mesh.m_VertexCount * 4)
            {
                c = 4;
            }
            for (int v = 0; v < m_Mesh.m_VertexCount; v++)
            {
                sb.AppendFormat("v {0} {1} {2}\r\n", -m_Mesh.m_Vertices[v * c], m_Mesh.m_Vertices[v * c + 1], m_Mesh.m_Vertices[v * c + 2]);
            }
            #endregion

            #region UV
            if (m_Mesh.m_UV0?.Length > 0)
            {
                c = 4;
                if (m_Mesh.m_UV0.Length == m_Mesh.m_VertexCount * 2)
                {
                    c = 2;
                }
                else if (m_Mesh.m_UV0.Length == m_Mesh.m_VertexCount * 3)
                {
                    c = 3;
                }
                for (int v = 0; v < m_Mesh.m_VertexCount; v++)
                {
                    sb.AppendFormat("vt {0} {1}\r\n", m_Mesh.m_UV0[v * c], m_Mesh.m_UV0[v * c + 1]);
                }
            }
            #endregion

            #region Normals
            if (m_Mesh.m_Normals?.Length > 0)
            {
                if (m_Mesh.m_Normals.Length == m_Mesh.m_VertexCount * 3)
                {
                    c = 3;
                }
                else if (m_Mesh.m_Normals.Length == m_Mesh.m_VertexCount * 4)
                {
                    c = 4;
                }
                for (int v = 0; v < m_Mesh.m_VertexCount; v++)
                {
                    sb.AppendFormat("vn {0} {1} {2}\r\n", -m_Mesh.m_Normals[v * c], m_Mesh.m_Normals[v * c + 1], m_Mesh.m_Normals[v * c + 2]);
                }
            }
            #endregion

            #region Face
            int sum = 0;
            for (var i = 0; i < m_Mesh.m_SubMeshes.Length; i++)
            {
                sb.AppendLine($"g {m_Mesh.m_Name}_{i}");
                int indexCount = (int)m_Mesh.m_SubMeshes[i].indexCount;
                var end = sum + indexCount / 3;
                for (int f = sum; f < end; f++)
                {
                    sb.AppendFormat("f {0}/{0}/{0} {1}/{1}/{1} {2}/{2}/{2}\r\n", m_Mesh.m_Indices[f * 3 + 2] + 1, m_Mesh.m_Indices[f * 3 + 1] + 1, m_Mesh.m_Indices[f * 3] + 1);
                }
                sum = end;
            }
            #endregion

            sb.Replace("NaN", "0");
            File.WriteAllText(exportFullPath, sb.ToString());
            return true;
        }

        public static bool ExportVideoClip(AssetItem item, string exportPath)
        {
            var m_VideoClip = (VideoClip)item.Asset;
            if (m_VideoClip.m_ExternalResources.m_Size > 0)
            {
                if (!TryExportFile(exportPath, item, Path.GetExtension(m_VideoClip.m_OriginalPath), out var exportFullPath))
                    return false;
                m_VideoClip.m_VideoData.WriteData(exportFullPath);
                return true;
            }
            return false;
        }

        public static bool ExportMovieTexture(AssetItem item, string exportPath)
        {
            var m_MovieTexture = (MovieTexture)item.Asset;
            if (!TryExportFile(exportPath, item, ".ogv", out var exportFullPath))
                return false;
            File.WriteAllBytes(exportFullPath, m_MovieTexture.m_MovieData);
            return true;
        }

        public static bool ExportSprite(AssetItem item, string exportPath)
        {
            var type = Properties.Settings.Default.convertType;
            if (!TryExportFile(exportPath, item, "." + type.ToString().ToLower(), out var exportFullPath))
                return false;
            var image = ((Sprite)item.Asset).GetImage();
            if (image != null)
            {
                using (image)
                {
                    using (var file = File.OpenWrite(exportFullPath))
                    {
                        image.WriteToStream(file, type);
                    }
                    return true;
                }
            }
            return false;
        }

        public static bool ExportJsonFile(AssetItem item, string exportPath)
        {
            if (!TryExportFile(exportPath, item, ".json", out var exportFullPath))
                return false;
            var str = JsonConvert.SerializeObject(item.Asset, Formatting.Indented);
            if (!string.IsNullOrEmpty(str) && str != "{}")
            {
            File.WriteAllText(exportFullPath, str);
            return true;
        }
            else
            {
                return ExportRawFile(item, exportPath);
            }
        }

        public static bool ExportRawFile(AssetItem item, string exportPath)
        {
            if (!TryExportFile(exportPath, item, ".dat", out var exportFullPath))
                return false;
            File.WriteAllBytes(exportFullPath, item.Asset.GetRawData());
            return true;
        }

        private static bool TryExportFile(string dir, AssetItem item, string extension, out string fullPath)
        {
            var fileName = FixFileName(item.Text);
            fullPath = Path.Combine(dir, fileName + extension);
            if (!File.Exists(fullPath))
            {
                Directory.CreateDirectory(dir);
                return true;
            }
            fullPath = Path.Combine(dir, fileName + item.UniqueID + extension);
            if (!File.Exists(fullPath))
            {
                Directory.CreateDirectory(dir);
                return true;
            }
            return false;
        }

        public static bool ExportAnimationClip(AssetItem item, string exportPath)
        {
            if (!TryExportFile(exportPath, item, ".anim", out var exportFullPath))
                return false;
            var m_AnimationClip = (AnimationClip)item.Asset;
            var str = m_AnimationClip.Convert(Studio.Game);
            File.WriteAllText(exportFullPath, str);
            return true;
        }

        public static bool ExportAnimator(AssetItem item, string exportPath, List<AssetItem> animationList = null)
        {
            var exportFullPath = Path.Combine(exportPath, item.Text, item.Text + ".fbx");
            if (File.Exists(exportFullPath))
            {
                exportFullPath = Path.Combine(exportPath, item.Text + item.UniqueID, item.Text + ".fbx");
            }
            var m_Animator = (Animator)item.Asset;
            var convert = animationList != null
                ? new ModelConverter(m_Animator, Properties.Settings.Default.convertType, Studio.Game, animationList.Select(x => (AnimationClip)x.Asset).ToArray(), Properties.Settings.Default.ignoreController)
                : new ModelConverter(m_Animator, Properties.Settings.Default.convertType, Studio.Game, ignoreController: Properties.Settings.Default.ignoreController);
            ExportFbx(convert, exportFullPath);
            return true;
        }

        public static void ExportGameObject(GameObject gameObject, string exportPath, List<AssetItem> animationList = null)
        {
            var convert = animationList != null
                ? new ModelConverter(gameObject, Properties.Settings.Default.convertType, Studio.Game, animationList.Select(x => (AnimationClip)x.Asset).ToArray(), Properties.Settings.Default.ignoreController)
                : new ModelConverter(gameObject, Properties.Settings.Default.convertType, Studio.Game, ignoreController: Properties.Settings.Default.ignoreController);
            exportPath = exportPath + FixFileName(gameObject.m_Name) + ".fbx";
            ExportFbx(convert, exportPath);
        }

        public static void ExportGameObjectMerge(List<GameObject> gameObject, string exportPath, List<AssetItem> animationList = null)
        {
            var rootName = Path.GetFileNameWithoutExtension(exportPath);
            var convert = animationList != null
                ? new ModelConverter(rootName, gameObject, Properties.Settings.Default.convertType, Studio.Game, animationList.Select(x => (AnimationClip)x.Asset).ToArray(), Properties.Settings.Default.ignoreController)
                : new ModelConverter(rootName, gameObject, Properties.Settings.Default.convertType, Studio.Game, ignoreController: Properties.Settings.Default.ignoreController);
            ExportFbx(convert, exportPath);
        }

        private static void ExportFbx(IImported convert, string exportPath)
        {
            var eulerFilter = Properties.Settings.Default.eulerFilter;
            var filterPrecision = (float)Properties.Settings.Default.filterPrecision;
            var exportAllNodes = Properties.Settings.Default.exportAllNodes;
            var exportSkins = Properties.Settings.Default.exportSkins;
            var exportAnimations = Properties.Settings.Default.exportAnimations;
            var exportBlendShape = Properties.Settings.Default.exportBlendShape;
            var castToBone = Properties.Settings.Default.castToBone;
            var boneSize = (int)Properties.Settings.Default.boneSize;
            var exportAllUvsAsDiffuseMaps = Properties.Settings.Default.exportAllUvsAsDiffuseMaps;
            var exportUV0UV1 = Properties.Settings.Default.exportUV0UV1;
            var scaleFactor = (float)Properties.Settings.Default.scaleFactor;
            var fbxVersion = Properties.Settings.Default.fbxVersion;
            var fbxFormat = Properties.Settings.Default.fbxFormat;
            ModelExporter.ExportFbx(exportPath, convert, eulerFilter, filterPrecision,
                exportAllNodes, exportSkins, exportAnimations, exportBlendShape, castToBone, boneSize, exportAllUvsAsDiffuseMaps, exportUV0UV1, scaleFactor, fbxVersion, fbxFormat == 1);
        }

        public static bool ExportDumpFile(AssetItem item, string exportPath)
        {
            if (!TryExportFile(exportPath, item, ".txt", out var exportFullPath))
                return false;
            var str = item.Asset.Dump();
            if (str == null && item.Asset is MonoBehaviour m_MonoBehaviour)
            {
                var m_Type = Studio.MonoBehaviourToTypeTree(m_MonoBehaviour);
                str = m_MonoBehaviour.Dump(m_Type);
            }
            if (str != null)
            {
                File.WriteAllText(exportFullPath, str);
                return true;
            }
            return false;
        }

        public static bool ExportConvertFile(AssetItem item, string exportPath)
        {
            switch (item.Type)
            {
                case ClassIDType.Texture2D:
                    return ExportTexture2D(item, exportPath);
                case ClassIDType.AudioClip:
                    return ExportAudioClip(item, exportPath);
                case ClassIDType.Shader:
                    return ExportShader(item, exportPath);
                case ClassIDType.TextAsset:
                    return ExportTextAsset(item, exportPath);
                case ClassIDType.MonoBehaviour:
                    return ExportMonoBehaviour(item, exportPath);
                case ClassIDType.Font:
                    return ExportFont(item, exportPath);
                case ClassIDType.Mesh:
                    return ExportMesh(item, exportPath);
                case ClassIDType.VideoClip:
                    return ExportVideoClip(item, exportPath);
                case ClassIDType.MovieTexture:
                    return ExportMovieTexture(item, exportPath);
                case ClassIDType.Sprite:
                    return ExportSprite(item, exportPath);
                case ClassIDType.Animator:
                    return ExportAnimator(item, exportPath);
                case ClassIDType.AnimationClip:
                    return ExportAnimationClip(item, exportPath);
                case ClassIDType.MiHoYoBinData:
                    return ExportMiHoYoBinData(item, exportPath);
                default:
                    return ExportJsonFile(item, exportPath);
            }
        }

        public static string FixFileName(string str)
        {
            if (str.Length >= 260) return Path.GetRandomFileName();
            return Path.GetInvalidFileNameChars().Aggregate(str, (current, c) => current.Replace(c, '_'));
        }
    }
}
