using System;
using System.Data;
using System.Configuration;
using System.Web;
using System.Web.Security;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Web.UI.WebControls.WebParts;
using System.Web.UI.HtmlControls;
using System.Data.SqlClient;
using EBS.Classes;
using EBS_Common.Classes;
using System.Text;

namespace EBS.Classes
{
    /// <summary>
    /// Summary description for clsHazard_ID_Card
    /// </summary>
    public class clsHazard_ID_Card : EBS_Common.Classes.clsCommonTableFields // inheriting common fields
    {
        #region Defining Local Variables - Class Level
        private SqlConnection Conn;
        private string strConnString = "";
        #endregion

        # region Defining Property Variables

        private Int16 _Haz_Card_Id;
        private Int16 _Haz_ID_Card_No;
        private Int16 _Prj_Contract_Id;
        private Int16 _Rig_Id;

        private string _Event_Dt;
        private string _Event_Time;
        private string _Reported_By_Party;
        private Int32? _Reported_By_Fs_Emp_Id;
        private string _Reported_By_Name;
        private byte _Work_Location_Id;
        private Int16 _Haz_Type_Id;
        private string _Timeout_For_Safety;
        private string _Hazard_Desc;
        private string _Action_Taken;
        private byte _Resp_Dept_Id;
        private byte _Resp_Rank_Id;
        private string _Close_Out_Dt;
        private string _Close_Out_Dt_Time;
        private string _Haz_ID_Card_Status;
        private string _Haz_ID_Card_Deleted;
        private string _Deleted_Remarks;



        #endregion

        #region Constructor

        public clsHazard_ID_Card(string constr)
        {
            strConnString = constr;
            Conn = new SqlConnection(strConnString);
        }

        #endregion

        # region Property Declarations


        public Int16 Haz_Card_Id
        {
            get
            {
                return _Haz_Card_Id;
            }
            set
            {
                _Haz_Card_Id = value;
            }
        }
        public Int16 Haz_ID_Card_No
        {
            get
            {
                return _Haz_ID_Card_No;
            }
            set
            {
                _Haz_ID_Card_No = value;
            }
        }
        public Int16 Prj_Contract_Id
        {
            get
            {
                return _Prj_Contract_Id;
            }
            set
            {
                _Prj_Contract_Id = value;
            }
        }
        public Int16 Rig_Id
        {
            get
            {
                return _Rig_Id;
            }
            set
            {
                _Rig_Id = value;
            }
        }
        public string Event_Dt
        {
            get
            {
                return _Event_Dt;
            }
            set
            {
                _Event_Dt = value;
            }
        }
        public string Event_Time
        {
            get
            {
                return _Event_Time;
            }
            set
            {
                _Event_Time = value;
            }
        }
        public string Reported_By_Party
        {
            get
            {
                return _Reported_By_Party;
            }
            set
            {
                _Reported_By_Party = value;
            }
        }
        public Int32? Reported_By_Fs_Emp_Id
        {
            get
            {
                return _Reported_By_Fs_Emp_Id;
            }
            set
            {
                _Reported_By_Fs_Emp_Id = value;
            }
        }
        public string Reported_By_Name
        {
            get
            {
                return _Reported_By_Name;
            }
            set
            {
                _Reported_By_Name = value;
            }
        }
        public byte Work_Location_Id
        {
            get
            {
                return _Work_Location_Id;
            }
            set
            {
                _Work_Location_Id = value;
            }
        }
        public Int16 Haz_Type_Id
        {
            get
            {
                return _Haz_Type_Id;
            }
            set
            {
                _Haz_Type_Id = value;
            }
        }
        public string Timeout_For_Safety
        {
            get
            {
                return _Timeout_For_Safety;
            }
            set
            {
                _Timeout_For_Safety = value;
            }
        }
        public string Hazard_Desc
        {
            get
            {
                return _Hazard_Desc;
            }
            set
            {
                _Hazard_Desc = value;
            }
        }
        public string Action_Taken
        {
            get
            {
                return _Action_Taken;
            }
            set
            {
                _Action_Taken = value;
            }
        }
        public byte Resp_Dept_Id
        {
            get
            {
                return _Resp_Dept_Id;
            }
            set
            {
                _Resp_Dept_Id = value;
            }
        }
        public byte Resp_Rank_Id
        {
            get
            {
                return _Resp_Rank_Id;
            }
            set
            {
                _Resp_Rank_Id = value;
            }
        }
        public string Close_Out_Dt
        {
            get
            {
                return _Close_Out_Dt;
            }
            set
            {
                _Close_Out_Dt = value;
            }
        }
        public string  Close_Out_Dt_Time
        {
            get
            {
                return _Close_Out_Dt_Time;
            }
            set
            {
                _Close_Out_Dt_Time= value;
            }
        }

    
        public string Haz_ID_Card_Status
        {
            get
            {
                return _Haz_ID_Card_Status;
            }
            set
            {
                _Haz_ID_Card_Status = value;
            }
        }
        public string Haz_ID_Card_Deleted
        {
            get
            {
                return _Haz_ID_Card_Deleted;
            }
            set
            {
                _Haz_ID_Card_Deleted = value;
            }
        } 

        public string Deleted_Remarks
        {
            get
            {
                return _Deleted_Remarks;
            }
            set
            {
               _Deleted_Remarks = value;
            }
        } 
        #endregion

        /// <summary>
        /// To insert a new record
        /// </summary>
        public void InsertMe()
        {
            SqlTransaction trDML;
            SqlCommand CmdDML;

            Conn.Open();
            trDML = Conn.BeginTransaction();
            try
            {

                CmdDML = new SqlCommand(OI.Def + "Prc_Hazard_ID_Card", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;

                CmdDML.Parameters.Add(new SqlParameter("Haz_Card_Id", SqlDbType.SmallInt));
                CmdDML.Parameters["Haz_Card_Id"].Direction = ParameterDirection.Output;  //Required afterward in file saving & Fs Interview Dtl storing logic.
          

                CmdDML.Parameters.Add("Prj_Contract_Id", System.Data.SqlDbType.SmallInt).Value = _Prj_Contract_Id;
                CmdDML.Parameters.Add("Rig_Id", System.Data.SqlDbType.SmallInt).Value = _Rig_Id;
                CmdDML.Parameters.Add("Event_Dt", System.Data.SqlDbType.DateTime).Value =
                Convert.ToDateTime(DateTime.ParseExact(_Event_Dt + " " + _Event_Time + ":00", "dd/MM/yyyy HH:mm:ss", null));

                CmdDML.Parameters.Add("Reported_By_Party", System.Data.SqlDbType.VarChar).Value = _Reported_By_Party;

                if (_Reported_By_Fs_Emp_Id.HasValue)
                    CmdDML.Parameters.Add("Reported_By_Fs_Emp_Id", System.Data.SqlDbType.Int).Value = _Reported_By_Fs_Emp_Id;
                else
                    CmdDML.Parameters.Add("Reported_By_Fs_Emp_Id", System.Data.SqlDbType.Int).Value = DBNull.Value;

                if (!string.IsNullOrEmpty(Reported_By_Name))
                    CmdDML.Parameters.Add("Reported_By_Name", System.Data.SqlDbType.VarChar).Value = _Reported_By_Name;
                else
                    CmdDML.Parameters.Add("Reported_By_Name", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                CmdDML.Parameters.Add("Work_Location_Id", System.Data.SqlDbType.TinyInt).Value = _Work_Location_Id;
                CmdDML.Parameters.Add("Haz_Type_Id", System.Data.SqlDbType.SmallInt).Value = _Haz_Type_Id;
                CmdDML.Parameters.Add("Timeout_For_Safety", System.Data.SqlDbType.VarChar).Value = _Timeout_For_Safety;
                CmdDML.Parameters.Add("Hazard_Desc", System.Data.SqlDbType.VarChar).Value = _Hazard_Desc;


                if (!string.IsNullOrEmpty(_Action_Taken))
                    CmdDML.Parameters.Add("Action_Taken", System.Data.SqlDbType.VarChar).Value = _Action_Taken;
                else
                    CmdDML.Parameters.Add("Action_Taken", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                CmdDML.Parameters.Add("Resp_Dept_Id", System.Data.SqlDbType.TinyInt).Value = _Resp_Dept_Id;
                CmdDML.Parameters.Add("Resp_Rank_Id", System.Data.SqlDbType.TinyInt).Value = _Resp_Rank_Id;

                if (!string.IsNullOrEmpty(_Close_Out_Dt))
                    CmdDML.Parameters.Add("Close_Out_Dt", System.Data.SqlDbType.DateTime).Value = Convert.ToDateTime(DateTime.ParseExact(_Close_Out_Dt + " " + _Close_Out_Dt_Time + ":00", "dd/MM/yyyy HH:mm:ss", null));
                else
                    CmdDML.Parameters.Add("Close_Out_Dt", System.Data.SqlDbType.DateTime).Value = DBNull.Value;


                CmdDML.Parameters.Add("Haz_ID_Card_Status", System.Data.SqlDbType.VarChar).Value = _Haz_ID_Card_Status;
                CmdDML.Parameters.Add("Cr_User_Id", System.Data.SqlDbType.SmallInt).Value = Cr_User_Id;
                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Insert";
                CmdDML.ExecuteNonQuery();


                string strHaz_Card_Id = CmdDML.Parameters["Haz_Card_Id"].Value.ToString();

                if (!string.IsNullOrEmpty(strHaz_Card_Id))
                {
                    _Haz_Card_Id = Convert.ToInt16(strHaz_Card_Id);
                }
                else
                {
                    throw new Exception(ErrorString);
                }


                trDML.Commit();
            }
            catch (SqlException Sqlexep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(Sqlexep, ref Conn);
            }
            catch (Exception exep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            }
            finally
            {
                if (Conn.State == ConnectionState.Open)
                {
                    Conn.Close();
                    Conn.Dispose();
                }
            }
        }
         
        public void UpdateMe()
        {
            SqlTransaction trDML;
            SqlCommand CmdDML;

            Conn.Open();
            trDML = Conn.BeginTransaction();
            try
            {

                CmdDML = new SqlCommand(OI.Def + "Prc_Hazard_ID_Card", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;
                CmdDML.Parameters.Add("Haz_Card_Id", System.Data.SqlDbType.SmallInt).Value = _Haz_Card_Id;
                 
                CmdDML.Parameters.Add("Prj_Contract_Id", System.Data.SqlDbType.SmallInt).Value = _Prj_Contract_Id;
                CmdDML.Parameters.Add("Rig_Id", System.Data.SqlDbType.SmallInt).Value = _Rig_Id;
                CmdDML.Parameters.Add("Event_Dt", System.Data.SqlDbType.DateTime).Value =
                Convert.ToDateTime(DateTime.ParseExact(_Event_Dt + " " + _Event_Time + ":00", "dd/MM/yyyy HH:mm:ss", null)); 

                CmdDML.Parameters.Add("Reported_By_Party", System.Data.SqlDbType.VarChar).Value = _Reported_By_Party;

                if (_Reported_By_Fs_Emp_Id.HasValue)
                    CmdDML.Parameters.Add("Reported_By_Fs_Emp_Id", System.Data.SqlDbType.Int).Value = _Reported_By_Fs_Emp_Id;
                else
                    CmdDML.Parameters.Add("Reported_By_Fs_Emp_Id", System.Data.SqlDbType.Int).Value = DBNull.Value;

                if (!string.IsNullOrEmpty(Reported_By_Name))
                    CmdDML.Parameters.Add("Reported_By_Name", System.Data.SqlDbType.VarChar).Value = _Reported_By_Name;
                else
                    CmdDML.Parameters.Add("Reported_By_Name", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                CmdDML.Parameters.Add("Work_Location_Id", System.Data.SqlDbType.TinyInt).Value = _Work_Location_Id;
                CmdDML.Parameters.Add("Haz_Type_Id", System.Data.SqlDbType.SmallInt).Value = _Haz_Type_Id;
                CmdDML.Parameters.Add("Timeout_For_Safety", System.Data.SqlDbType.VarChar).Value = _Timeout_For_Safety;
                CmdDML.Parameters.Add("Hazard_Desc", System.Data.SqlDbType.VarChar).Value = _Hazard_Desc;


                if (!string.IsNullOrEmpty(_Action_Taken))
                    CmdDML.Parameters.Add("Action_Taken", System.Data.SqlDbType.VarChar).Value = _Action_Taken;
                else
                    CmdDML.Parameters.Add("Action_Taken", System.Data.SqlDbType.VarChar).Value = DBNull.Value;

                CmdDML.Parameters.Add("Resp_Dept_Id", System.Data.SqlDbType.TinyInt).Value = _Resp_Dept_Id;
                CmdDML.Parameters.Add("Resp_Rank_Id", System.Data.SqlDbType.TinyInt).Value = _Resp_Rank_Id;

                if (!string.IsNullOrEmpty(_Close_Out_Dt))
                    CmdDML.Parameters.Add("Close_Out_Dt", System.Data.SqlDbType.DateTime).Value = Convert.ToDateTime(DateTime.ParseExact(_Close_Out_Dt + " " + _Close_Out_Dt_Time + ":00", "dd/MM/yyyy HH:mm:ss", null));
                else
                    CmdDML.Parameters.Add("Close_Out_Dt", System.Data.SqlDbType.DateTime).Value = DBNull.Value;

                CmdDML.Parameters.Add("Haz_ID_Card_Status", System.Data.SqlDbType.VarChar).Value = _Haz_ID_Card_Status;
 
                CmdDML.Parameters.Add("Mod_User_Id", System.Data.SqlDbType.SmallInt).Value = Mod_User_Id;
                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Update";
                CmdDML.ExecuteNonQuery();
                trDML.Commit();
            }
            catch (SqlException Sqlexep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(Sqlexep, ref Conn);
            }
            catch (Exception exep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            }
            finally
            {
                if (Conn.State == ConnectionState.Open)
                {
                    Conn.Close();
                    Conn.Dispose();
                }
            }
        }
 
        public void DeleteMe()
        {
            SqlTransaction trDML;
            SqlCommand CmdDML;

            Conn.Open();
            trDML = Conn.BeginTransaction();
            try
            {
                ///Dont 
                CmdDML = new SqlCommand(OI.Def + "Prc_Hazard_ID_Card", Conn, trDML);
                CmdDML.CommandType = CommandType.StoredProcedure;

                CmdDML.Parameters.Add("Haz_Card_Id", System.Data.SqlDbType.SmallInt).Value = _Haz_Card_Id;

                if (!string.IsNullOrEmpty(_Deleted_Remarks))
                    CmdDML.Parameters.Add("Deleted_Remarks", System.Data.SqlDbType.VarChar).Value = _Deleted_Remarks;
                else
                    CmdDML.Parameters.Add("Deleted_Remarks", System.Data.SqlDbType.VarChar).Value = DBNull.Value;
     
            
                CmdDML.Parameters.Add("Mod_User_Id", System.Data.SqlDbType.SmallInt).Value = Mod_User_Id;
                CmdDML.Parameters.Add("Record_Status", System.Data.SqlDbType.VarChar).Value = "Delete";
                CmdDML.ExecuteNonQuery();
                trDML.Commit();
            }

            catch (SqlException Sqlexep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(Sqlexep, ref Conn);
            }
            catch (Exception exep)
            {
                trDML.Rollback();
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            }
            finally
            {
                if (Conn.State == ConnectionState.Open)
                {
                    Conn.Close();
                    Conn.Dispose();
                }
            }
        }
    }
}